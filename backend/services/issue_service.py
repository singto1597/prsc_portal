import asyncpg
import json
from typing import Optional
from datetime import datetime, timedelta, timezone

from core.exceptions import NotFoundError, ForbiddenError, ValidationError
from core.config import settings
from core.categories import is_valid_category, all_main_category_codes

# 🔼 ลำดับการ Escalate (พีระมิด)
# room (หัวหน้าห้อง+รอง) → level (ประธานระดับ) → council (สภานักเรียน)
LEVEL_ORDER = ["room", "level", "council"]
NEXT_LEVEL = {"room": "level", "level": "council"}

# ตำแหน่งที่รับเรื่องได้ในแต่ละระดับ (role key → ระดับ)
ROLE_LEVEL = {
    "class_president": "room",
    "vice_academic": "room",
    "vice_discipline": "room",
    "vice_activity": "room",
    "vice_reception": "room",
    "level_president": "level",
    "council_member": "council",
    "council_president": "council",
}

# ระดับ 'student' (นักเรียนธรรมดา) อยู่ต่ำกว่าทุกอย่าง
LEVEL_RANK = {"student": 0, "room": 1, "level": 2, "council": 3}


def _parse_permissions(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
    return list(raw)


def _parse_json(raw, default=None):
    if raw is None:
        return default if default is not None else []
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default if default is not None else []


def _escape_like(s: str) -> str:
    """หนี wildcard ของ LIKE/ILIKE (% _ \\) ให้ค้นหาคำที่เป็นตัวอักษรจริง (กัน %/_ กลายเป็น wildcard)
    ใช้คู่กับ `ILIKE ... ESCAPE '\\'` ใน query"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ============================================================
# 👩‍🏫 Helpers สำหรับครูทั่วไป (level-scoped teacher)
# ============================================================
async def _teacher_scope(conn, user_id: int) -> Optional[str]:
    """คืนระดับชั้นที่ครูทั่วไปรับผิดชอบ (เช่น 'ม.4') หรือ None ถ้าไม่ใช่ครูทั่วไป"""
    row = await conn.fetchrow(
        """
        SELECT staff_level FROM students
        WHERE user_id = $1 AND class_role = 'teacher'
          AND deleted_at IS NULL AND status = 'active'
        ORDER BY id LIMIT 1
        """,
        user_id
    )
    return row["staff_level"] if row and row["staff_level"] else None


async def _room_level(conn, room_id: Optional[int]) -> Optional[str]:
    """คืนระดับชั้น (เช่น 'ม.4') ของห้อง"""
    if not room_id:
        return None
    return await conn.fetchval("SELECT level FROM rooms WHERE id = $1", room_id)


async def _level_room_ids(conn, staff_level: str) -> list:
    """คืน id ห้องทั้งหมดที่อยู่ในระดับชั้นที่กำหนด"""
    rows = await conn.fetch(
        "SELECT id FROM rooms WHERE level = $1 AND deleted_at IS NULL",
        staff_level
    )
    return [r["id"] for r in rows]


async def _can_manage_issue(conn, user_id: int, issue) -> bool:
    """
    เช็คว่า user จัดการเรื่องนี้ได้หรือไม่:
    - ผู้รับเรื่องปัจจุบัน
    - admin (is_admin / SUPER_ADMIN)
    - ครูทั่วไปที่รับผิดชอบระดับชั้นเดียวกับเรื่อง
    """
    if issue["current_assignee_id"] == user_id:
        return True
    if await _is_admin(conn, user_id):
        return True
    teacher_level = await _teacher_scope(conn, user_id)
    if teacher_level:
        room_level = await _room_level(conn, issue["room_id"])
        if room_level == teacher_level:
            return True
    return False


# ============================================================
# 🔍 ความสามารถในการมองเห็น (Pyramid Visibility)
# ============================================================
async def user_level(pool, user_id: int, room_id: Optional[int] = None) -> str:
    """
    คืนระดับสูงสุดที่ user สังกัด (room / level / council)
    - ถ้าระบุ room_id → ดูเฉพาะในห้องนั้น
    - ถ้าไม่ระบุ → ดูทุกตำแหน่งที่ user เป็น (คืนระดับสูงสุด)
    - ครูทั่วไป → คืน "council" (มองเห็นสูงสุด แต่ถูกจำกัดระดับชั้นใน list/get)
    """
    async with pool.acquire() as conn:
        if room_id is not None:
            row = await conn.fetchrow(
                """
                SELECT class_role FROM students
                WHERE user_id = $1 AND room_id = $2 AND deleted_at IS NULL AND status = 'active'
                """,
                user_id, room_id
            )
            role = row["class_role"] if row else None
        else:
            rows = await conn.fetch(
                """
                SELECT class_role FROM students
                WHERE user_id = $1 AND deleted_at IS NULL AND status = 'active'
                """,
                user_id
            )
            roles = [r["class_role"] for r in rows]

            # SUPER_ADMIN มองเห็นทุกอย่าง
            if settings.SUPER_ADMIN_ID and int(user_id) == int(settings.SUPER_ADMIN_ID):
                return "council"

            # admin / ครูสภา / ประธานสภา: มองเห็นทุกอย่าง (เทียบเท่า council สูงสุด)
            if any(r in ("admin", "teacher_council", "council_president") for r in roles):
                return "council"

            # ครูทั่วไป: มองเห็นระดับสูงสุด แต่ scope ถูกจำกัดระดับชั้นที่อื่น
            if "teacher" in roles:
                return "council"

            # หาระดับสูงสุดจากทุกตำแหน่ง (ใช้ LEVEL_RANK รองรับ 'student')
            levels = [ROLE_LEVEL.get(r, "student") for r in roles]
            best = "student"
            for lv in levels:
                if LEVEL_RANK.get(lv, 0) > LEVEL_RANK.get(best, 0):
                    best = lv
            return best

    if not role:
        return "student"
    return ROLE_LEVEL.get(role, "student")


def can_see(level: str, issue_level: str, reporter_id: int, user_id: int, is_anonymous: bool) -> bool:
    """
    กฎการมองเห็น (พีระมิด):
    - ระดับที่สูงกว่า มองเห็นเรื่องของระดับล่างลงมา (มองลงได้)
    - ผู้แจ้งเห็นเรื่องของตัวเองเสมอ (ติดตามสถานะได้ แม้แจ้งแบบ anonymous)
    - anonymity แค่ซ่อนชื่อจากคนอื่น (ระบบรู้ผู้แจ้ง แต่คนอื่นเห็นเป็น "ไม่ระบุชื่อ")
    """
    # ระดับสูงกว่ามองลงได้ทุกเรื่อง
    if LEVEL_RANK.get(level, 0) >= LEVEL_RANK.get(issue_level, 1):
        return True
    # ผู้แจ้งเห็นเรื่องของตัวเองเสมอ (ติดตามสถานะ)
    if reporter_id == user_id:
        return True
    return False


# ============================================================
# 📝 CRUD ปัญหา
# ============================================================
async def create_issue(
    pool: asyncpg.Pool,
    user_id: int,
    main_category: str,
    category: str,
    title: str,
    description: str,
    is_anonymous: bool = False,
    room_id: Optional[int] = None,
    start_level: str = "room",
) -> int:
    """
    สร้างปัญหาใหม่
    - เริ่มต้นที่ระดับ room (หัวหน้าห้อง + รอง) โดยค่า default
    - ถ้าผู้แจ้งเป็นระดับสูง (หัวหน้าห้อง/ประธานระดับ/สภา) สามารถเลือก start_level
      ให้เรื่องไปเริ่มที่ระดับสูงขึ้นได้เลย (เช่น ประธานสภาอยากให้เริ่มที่ council)
    - main_category: หมวดหลัก (suggestion/wellbeing/report), category: หมวดย่อยในหมวดหลัก
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            # ตรวจ start_level ถูกต้อง
            if start_level not in LEVEL_ORDER:
                raise ValidationError(f"ระดับเริ่มต้นไม่ถูกต้อง: {start_level}")

            # ✅ ตรวจหมวดหมู่: หมวดย่อยต้องเป็นของหมวดหลักที่ระบุ
            if not is_valid_category(main_category, category):
                raise ValidationError(f"หมวดหมู่ไม่ถูกต้อง: หมวดหลัก '{main_category}' ไม่มีหมวดย่อย '{category}'")

            # ถ้าไม่ระบุห้อง → หาห้องของ user
            if not room_id:
                room_id = await conn.fetchval(
                    """
                    SELECT room_id FROM students
                    WHERE user_id = $1 AND deleted_at IS NULL AND status = 'active'
                    ORDER BY id LIMIT 1
                    """,
                    user_id
                )
                if not room_id:
                    raise ValidationError("ไม่พบห้องของคุณ — กรุณาติดต่อผู้ดูแล")

            # ตรวจว่าห้องมีจริง
            room = await conn.fetchrow(
                "SELECT id, room_name FROM rooms WHERE id = $1 AND deleted_at IS NULL",
                room_id
            )
            if not room:
                raise NotFoundError("ไม่พบห้องเรียน")

            # 🛡️ ผู้แจ้งต้องมีสิทธิ์ในระดับที่เลือกเริ่มต้น (ไม่งั้นนักเรียนธรรมดาส่งขึ้นสภาได้)
            if start_level != "room":
                my_level = await user_level(pool, user_id, room_id=room_id)
                if LEVEL_RANK.get(my_level, 0) < LEVEL_RANK.get(start_level, 1):
                    raise ForbiddenError(f"คุณมีสิทธิ์แค่ระดับ {my_level} — ไม่สามารถเริ่มที่ระดับ {start_level} ได้")

            reporter_name = None
            if not is_anonymous:
                reporter_name = await conn.fetchval(
                    """
                    SELECT CONCAT_WS(' ', prefix, first_name, last_name)
                    FROM students
                    WHERE user_id = $1 AND room_id = $2 AND deleted_at IS NULL
                    """,
                    user_id, room_id
                )

            issue_id = await conn.fetchval(
                """
                INSERT INTO issues
                    (room_id, main_category, category, title, description,
                     reporter_id, reporter_room_id, reporter_name,
                     current_level, current_assignee_id, status,
                     is_anonymous)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NULL, 'pending', $10)
                RETURNING id
                """,
                room_id, main_category, category, title, description,
                user_id, room_id, reporter_name,
                start_level,
                is_anonymous
            )

            # บันทึก status history (บอกว่าออกที่ระดับไหน)
            note = f"สร้างเรื่องใหม่ (เริ่มต้นที่ระดับ {start_level})"
            await conn.execute(
                """
                INSERT INTO issue_status_history (issue_id, status, changed_by, note)
                VALUES ($1, 'pending', $2, $3)
                """,
                issue_id, user_id, note
            )

            # ถ้า start_level สูงกว่า room → บันทึก escalation เป็นประวัติด้วย
            if start_level != "room":
                await conn.execute(
                    """
                    INSERT INTO issue_escalations (issue_id, from_level, to_level, from_assignee_id, reason)
                    VALUES ($1, 'room', $2, $3, 'ผู้แจ้งเลือกเริ่มต้นที่ระดับนี้โดยตรง')
                    """,
                    issue_id, start_level, user_id
                )

            return issue_id


async def update_issue(
    pool: asyncpg.Pool,
    user_id: int,
    issue_id: int,
    *,
    main_category: Optional[str] = None,
    category: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    is_anonymous: Optional[bool] = None,
) -> None:
    """
    แก้ไขเรื่องโดยผู้แจ้ง (หรือ admin)
    - แก้ได้เฉพาะตอนสถานะยังไม่ปิด: pending / in_progress / escalated
      (ปิดแล้ว = resolved / cancelled / rejected → ห้ามแก้)
    - PATCH: รับเฉพาะฟิลด์ที่ส่งมา (exclude_unset) — อย่าเขียนทับค่าที่ไม่ได้ส่ง
    - ถ้าเปิดเผยชื่อ (is_anonymous True→False) และ reporter_name ว่าง → re-snapshot จาก students
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            # SELECT ... FOR UPDATE กัน TOCTOU กับ resolve/cancel/accept (ทุกอัน UPDATE แถวนี้)
            issue = await conn.fetchrow(
                "SELECT * FROM issues WHERE id = $1 AND deleted_at IS NULL FOR UPDATE",
                issue_id
            )
            if not issue:
                raise NotFoundError("ไม่พบเรื่องนี้")

            # 1) สิทธิ์: ผู้แจ้งเท่านั้น (+ admin bypass ตาม _is_admin)
            if issue["reporter_id"] != user_id and not await _is_admin(conn, user_id):
                raise ForbiddenError("เฉพาะผู้แจ้งเรื่องเท่านั้นที่แก้ไขเรื่องนี้ได้")

            # 2) สถานะปิด → แก้ไม่ได้
            if issue["status"] in ("resolved", "cancelled", "rejected"):
                raise ValidationError(
                    "เรื่องนี้อยู่ในสถานะปิดแล้ว (แก้ไขเสร็จ/ยกเลิก/ถูกปัดตก) — แก้ไขข้อมูลไม่ได้"
                )

            # 3) เก็บเฉพาะฟิลด์ที่ส่ง
            changed = {}
            if main_category is not None:
                changed["main_category"] = main_category
            if category is not None:
                changed["category"] = category
            if title is not None:
                changed["title"] = title
            if description is not None:
                changed["description"] = description
            if is_anonymous is not None:
                changed["is_anonymous"] = is_anonymous
            if not changed:
                raise ValidationError("ไม่มีข้อมูลที่ต้องการแก้ไข")

            # 4) re-validate หมวดหมู่กับคู่ที่มีผลจริง (อ้างอิง DB ถ้า field นั้นไม่ส่ง)
            eff_main = changed.get("main_category", issue["main_category"])
            eff_cat = changed.get("category", issue["category"])
            if not is_valid_category(eff_main, eff_cat):
                raise ValidationError(
                    f"หมวดหมู่ไม่ถูกต้อง: หมวดหลัก '{eff_main}' ไม่มีหมวดย่อย '{eff_cat}'"
                )

            # 5) dynamic SET — $1 สงวนไว้ WHERE id, field ถัดไปเริ่ม $len+1
            params = [issue_id]
            sets = []
            for key in ("main_category", "category", "title", "description", "is_anonymous"):
                if key in changed:
                    sets.append(f"{key} = ${len(params) + 1}")
                    params.append(changed[key])

            # 6) is_anonymous True→False: re-snapshot reporter_name ถ้ายังว่าง
            #    ใช้ reporter_id/reporter_room_id ของเรื่อง (ไม่ใช่ actor — admin แก้แทนได้)
            new_is_anonymous = changed.get("is_anonymous", issue["is_anonymous"])
            if issue["is_anonymous"] and not new_is_anonymous and not issue["reporter_name"]:
                reporter_room_id = issue["reporter_room_id"] or issue["room_id"]
                reporter_name = await _student_display_name(conn, issue["reporter_id"], reporter_room_id)
                if reporter_name:
                    sets.append(f"reporter_name = ${len(params) + 1}")
                    params.append(reporter_name)
                    changed["reporter_name"] = reporter_name

            sets.append("updated_at = NOW()")
            await conn.execute(
                f"UPDATE issues SET {', '.join(sets)} WHERE id = $1",
                *params
            )

            # 7) บันทึกใน status_history ว่าโดนแก้ (mirror create_issue)
            await conn.execute(
                """
                INSERT INTO issue_status_history (issue_id, status, changed_by, note)
                VALUES ($1, $2, $3, $4)
                """,
                issue_id, issue["status"], user_id, "ผู้แจ้งแก้ไขข้อมูลเรื่อง"
            )

            # 8) audit log ใน transaction เดียวกัน (ตามกฎ backend.md)
            old = {k: issue[k] for k in changed if k != "reporter_name"}
            new = {k: changed[k] for k in old}
            if "reporter_name" in changed:
                old["reporter_name"] = issue["reporter_name"]
                new["reporter_name"] = changed["reporter_name"]
            from core.logger import AuditLogger
            await AuditLogger("issue_service").log(
                conn=conn, action="UPDATE_ISSUE",
                actor_identifier=str(user_id), client_source="web",
                room_id=issue["room_id"], user_id=user_id,
                entity_type="issue", entity_id=issue_id,
                old_values=old, new_values=new,
            )


async def _assert_can_view(conn, pool: asyncpg.Pool, user_id: int, issue_row) -> None:
    """ตรวจว่า user มองเห็นเรื่องนี้ได้ไหม (พีระมิด + อดีตผู้รับ/ผู้เกี่ยวข้อง + ครูระดับชั้น)
    ใช้ร่วมกันระหว่าง get_issue และคอมเมนต์ เพื่อไม่ให้ visibility rule เบน"""
    level = await user_level(pool, user_id)
    involved = await _is_involved(conn, user_id, issue_row)
    visible = can_see(level, issue_row["current_level"], issue_row["reporter_id"], user_id, issue_row["is_anonymous"]) or involved

    # ครูทั่วไป: เห็นเฉพาะเรื่องของระดับชั้นตัวเอง (ยกเว้นเรื่องที่เกี่ยวข้อง/จัดการอยู่)
    teacher_level = await _teacher_scope(conn, user_id)
    if teacher_level:
        issue_level = await _room_level(conn, issue_row["room_id"])
        if issue_level != teacher_level and not involved:
            visible = False

    if not visible:
        raise ForbiddenError("คุณไม่มีสิทธิ์ดูเรื่องนี้")


async def get_issue(pool: asyncpg.Pool, user_id: int, issue_id: int) -> Optional[dict]:
    """ดึงปัญหาตาม id (ตรวจ visibility)"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                i.*,
                r.room_name,
                reporter_r.room_name AS reporter_room,
                u.full_name AS assignee_name
            FROM issues i
            JOIN rooms r ON r.id = i.room_id
            LEFT JOIN rooms reporter_r ON reporter_r.id = i.reporter_room_id
            LEFT JOIN users u ON u.id = i.current_assignee_id
            WHERE i.id = $1 AND i.deleted_at IS NULL
            """,
            issue_id
        )
        if not row:
            raise NotFoundError("ไม่พบเรื่องนี้")

        # ตรวจ visibility (พีระมิด + อดีตผู้รับ/ผู้เกี่ยวข้อง)
        await _assert_can_view(conn, pool, user_id, row)

        # ดึงรายละเอียดเสริม
        steps = await conn.fetch(
            "SELECT * FROM issue_steps WHERE issue_id = $1 ORDER BY step_order",
            issue_id
        )
        countdown = await conn.fetchrow(
            "SELECT * FROM issue_countdowns WHERE issue_id = $1 ORDER BY id DESC LIMIT 1",
            issue_id
        )
        escalations = await conn.fetch(
            """
            SELECT e.*, fu.full_name AS from_name, tu.full_name AS to_name
            FROM issue_escalations e
            LEFT JOIN users fu ON fu.id = e.from_assignee_id
            LEFT JOIN users tu ON tu.id = e.to_assignee_id
            WHERE e.issue_id = $1 ORDER BY e.created_at
            """,
            issue_id
        )
        history = await conn.fetch(
            "SELECT * FROM issue_status_history WHERE issue_id = $1 ORDER BY created_at",
            issue_id
        )
        comments = await conn.fetch(
            """
            SELECT * FROM issue_comments
            WHERE issue_id = $1 AND deleted_at IS NULL
            ORDER BY created_at, id
            """,
            issue_id
        )

        result = _issue_to_dict(row, with_details=True)
        result["steps"] = [_step_to_dict(s) for s in steps]
        result["countdown"] = _countdown_to_dict(countdown) if countdown else None
        result["escalations"] = [_esc_to_dict(e) for e in escalations]
        result["status_history"] = [_history_to_dict(h) for h in history]
        result["comments"] = [_comment_to_dict(c) for c in comments]
        return result


async def list_issues(
    pool: asyncpg.Pool,
    user_id: int,
    *,
    only_mine: bool = False,
    received: bool = False,
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    main_category: Optional[str] = None,
    level_filter: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = "desc",
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    รายการปัญหา — filter visibility ตามระดับผู้ใช้ + ค้นหา + แบ่งหน้า

    received=True: แสดงทุกเรื่องที่ผู้ใช้มองเห็นได้ (พีระมิด — ระดับสูงมองลงเห็นทุกระดับล่าง)
    main_category: กรองตามหมวดหลัก (suggestion / wellbeing / report) — ใช้จาก Dashboard
    level_filter: จำกัดให้ดูเฉพาะระดับที่เลือก (room/level/council)
    q: ค้นหาแบบคำต่อคำ (ILIKE partial match) ในชื่อเรื่อง/คำอธิบาย/ห้อง/ชื่อคน —
       อยู่ในขอบเขต visibility เดียวกับ list ปกติ (ค้นได้เฉพาะที่ตัวเองมองเห็น)
    sort: 'asc' = เก่าไปใหม่, 'desc' (default) = ใหม่ไปเก่า
    คืน {"items": [...], "total": N} — total นับก่อน limit/offset (COUNT(*) OVER())
    """
    level = await user_level(pool, user_id)

    async with pool.acquire() as conn:
        # เช็คว่า user อยู่ในห้องไหนบ้าง
        rooms = await conn.fetch(
            "SELECT room_id FROM students WHERE user_id = $1 AND deleted_at IS NULL AND status = 'active'",
            user_id
        )
        room_ids = [r["room_id"] for r in rooms]

        where = ["i.deleted_at IS NULL"]
        params = []

        # ---- ประยุกต์ use-case ----
        if only_mine:
            # เรื่องที่ฉันแจ้งเท่านั้น (ไม่ต้องสร้าง visible_cond — กัน param เกิน)
            params.append(user_id)
            where.append(f"i.reporter_id = ${len(params)}")
        else:
            # 👩‍🏫 ครูทั่วไป: เห็นเฉพาะเรื่องของระดับชั้นตัวเอง (พีระมิดสูงสุดแต่จำกัดชั้น)
            teacher_level = await _teacher_scope(conn, user_id)
            if teacher_level:
                teacher_room_ids = await _level_room_ids(conn, teacher_level)
                if not teacher_room_ids:
                    # ไม่มีห้องในระดับชั้นที่ดูแล → ไม่เห็นเรื่องใดเลย
                    where.append("1 = 0")
                else:
                    params.append(tuple(teacher_room_ids))
                    pyramid_cond = f"i.room_id = ANY(${len(params)})"
                    # + เรื่องที่เกี่ยวข้อง (เคยรับ/แจ้งเอง) แม้คนละระดับชั้น
                    params.append(user_id)
                    involved_cond = (
                        f"i.reporter_id = ${len(params)}"
                        f" OR i.current_assignee_id = ${len(params)}"
                        f" OR EXISTS (SELECT 1 FROM issue_escalations e WHERE e.issue_id = i.id AND e.from_assignee_id = ${len(params)})"
                        f" OR EXISTS (SELECT 1 FROM issue_countdowns cd WHERE cd.issue_id = i.id AND cd.assignee_id = ${len(params)})"
                    )
                    visible_cond = f"({pyramid_cond} OR ({involved_cond}))"
                    where.append(visible_cond)
            elif level == "student":
                # นักเรียนเห็นเรื่องของตัวเอง (รวม anonymous — ติดตามสถานะได้)
                params.append(user_id)
                visible_cond = f"i.reporter_id = ${len(params)}"
                where.append(visible_cond)
            else:
                # ระดับสูงกว่ามองลงได้ทุกระดับต่ำกว่า (พีระมิด)
                level_num = LEVEL_RANK.get(level, 1)  # 1=room, 2=level, 3=council
                params.append(level_num)
                pyramid_cond = (
                    f"CASE i.current_level WHEN 'room' THEN 1 WHEN 'level' THEN 2 WHEN 'council' THEN 3 ELSE 0 END <= ${len(params)}"
                )
                # ห้องของ user (สำหรับเรื่องในระดับ room)
                if room_ids and level == "room":
                    params.append(tuple(room_ids))
                    pyramid_cond += f" AND i.room_id = ANY(${len(params)})"

                # + เรื่องที่ user เกี่ยวข้อง (เคยรับ/อยู่ในห้องผู้แจ้ง) แม้ถูก escalate ขึ้นไปแล้ว
                params.append(user_id)
                involved_cond = (
                    f"i.reporter_id = ${len(params)}"
                    f" OR i.current_assignee_id = ${len(params)}"
                    f" OR EXISTS (SELECT 1 FROM issue_escalations e WHERE e.issue_id = i.id AND e.from_assignee_id = ${len(params)})"
                    f" OR EXISTS (SELECT 1 FROM issue_countdowns cd WHERE cd.issue_id = i.id AND cd.assignee_id = ${len(params)})"
                )
                visible_cond = f"({pyramid_cond} OR ({involved_cond}))"
                where.append(visible_cond)

        # ---- ตัวกรอง ----
        if status_filter:
            # รองรับหลายสถานะคั่นด้วย "," (เช่น "pending,in_progress,escalated")
            # ใช้กับฟิลเตอร์ "ยังไม่เสร็จ" ของหน้า ReceivedIssues — กรองฝั่ง server ไม่ใช่ตัด client
            status_list = [s.strip() for s in status_filter.split(",") if s.strip()]
            if len(status_list) > 1:
                params.append(status_list)
                where.append(f"i.status = ANY(${len(params)}::text[])")
            else:
                params.append(status_filter)
                where.append(f"i.status = ${len(params)}")
        if category:
            params.append(category)
            where.append(f"i.category = ${len(params)}")
        if main_category:
            # ตรวจหมวดหลัก (กันค่าแปลก → 400 แทน 500)
            if main_category not in all_main_category_codes():
                raise ValueError(f"หมวดหลักไม่ถูกต้อง: {main_category}")
            params.append(main_category)
            where.append(f"i.main_category = ${len(params)}")
        if level_filter:
            # กรองตามระดับปัจจุบันของเรื่อง (ถ้าระบุ) — ต้องอยู่ในระดับที่มองเห็นเท่านั้น
            if level_filter not in LEVEL_ORDER:
                raise ValueError(f"ระดับไม่ถูกต้อง: {level_filter}")
            params.append(level_filter)
            where.append(f"i.current_level = ${len(params)}")

        # ---- 🔍 ค้นหาแบบคำต่อคำ (ILIKE partial match) — ต่อ AFTER visibility กันค้นข้ามระดับ ----
        # ทุกคำ (แยกด้วยช่องว่าง) ต้องเจออย่างน้อย 1 ใน 6 ฟิลด์: ชื่อเรื่อง / คำอธิบาย / ห้อง / ชื่อคน
        # ใช้ $n เดียวซ้ำใน OR ได้ — ทุกตำแหน่งเป็น text จึงปลอดภัยกับ asyncpg
        if q:
            for token in q.split():
                esc = _escape_like(token)
                if not esc:
                    continue
                params.append(f"%{esc}%")
                n = len(params)
                where.append(
                    f"(i.title ILIKE ${n} ESCAPE '\\'"
                    f" OR i.description ILIKE ${n} ESCAPE '\\'"
                    f" OR r.room_name ILIKE ${n} ESCAPE '\\'"
                    f" OR reporter_r.room_name ILIKE ${n} ESCAPE '\\'"
                    f" OR COALESCE(i.reporter_name, '') ILIKE ${n} ESCAPE '\\'"
                    f" OR COALESCE(u.full_name, '') ILIKE ${n} ESCAPE '\\')"
                )

        # เก็บ params ของตัวกรองไว้ก่อน (ไม่รวม limit/offset) — ใช้กับ count query ตอนหน้าว่าง
        filter_params = list(params)

        params.append(limit)
        params.append(offset)
        sql = f"""
            SELECT
                i.id, i.room_id, i.main_category, i.category, i.title, i.description,
                i.image_url, i.reporter_id, i.reporter_name, i.current_level,
                i.current_assignee_id, i.current_assignee_role, i.status, i.priority,
                i.is_anonymous, i.resolved_at, i.created_at, i.updated_at,
                r.room_name,
                reporter_r.room_name AS reporter_room,
                u.full_name AS assignee_name,
                COUNT(*) OVER() AS total_count
            FROM issues i
            JOIN rooms r ON r.id = i.room_id
            LEFT JOIN rooms reporter_r ON reporter_r.id = i.reporter_room_id
            LEFT JOIN users u ON u.id = i.current_assignee_id
            WHERE {' AND '.join(where)}
            ORDER BY i.created_at {'ASC' if sort == 'asc' else 'DESC'}, i.id {'ASC' if sort == 'asc' else 'DESC'}
            LIMIT ${len(params)-1} OFFSET ${len(params)}
        """
        rows = await conn.fetch(sql, *params)

        # total: ปกติได้จาก COUNT(*) OVER() (แถวแรก) — แต่ถ้า offset เลยข้อมูล (rows ว่าง)
        # window function อ่านค่าไม่ได้ → นับแยกด้วย query เดียวกัน (ไม่มี limit/offset)
        if rows:
            total = rows[0]["total_count"]
        else:
            total = await conn.fetchval(
                f"""
                SELECT COUNT(*)
                FROM issues i
                JOIN rooms r ON r.id = i.room_id
                LEFT JOIN rooms reporter_r ON reporter_r.id = i.reporter_room_id
                LEFT JOIN users u ON u.id = i.current_assignee_id
                WHERE {' AND '.join(where)}
                """,
                *filter_params
            )

    return {"items": [_issue_to_dict(r) for r in rows], "total": total}


def _issue_to_dict(row, with_details=False) -> dict:
    """แปลงแถว issues → dict ตาม IssueOut shape"""
    d = {
        "id": row["id"],
        "room_id": row["room_id"],
        "room_name": row.get("room_name"),
        "main_category": row["main_category"],
        "category": row["category"],
        "title": row["title"],
        "description": row["description"],
        "image_url": row["image_url"],
        "reporter_id": row["reporter_id"],
        "reporter_name": row["reporter_name"] if not row["is_anonymous"] else None,
        "reporter_room": row.get("reporter_room") if not row["is_anonymous"] else None,
        "current_level": row["current_level"],
        "current_assignee_id": row["current_assignee_id"],
        "current_assignee_role": row["current_assignee_role"],
        "current_assignee_name": row.get("assignee_name"),
        "status": row["status"],
        "priority": row["priority"],
        "is_anonymous": row["is_anonymous"],
        "resolved_at": row["resolved_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if with_details:
        d["steps"] = []
        d["countdown"] = None
        d["escalations"] = []
        d["status_history"] = []
        d["comments"] = []
    return d


# ============================================================
# 👤 รับเรื่อง + Countdown
# ============================================================
async def accept_issue(pool: asyncpg.Pool, user_id: int, issue_id: int, estimated_days: int) -> None:
    """รับเรื่อง + ตั้ง countdown (วันใช้แก้ปัญหา)"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            issue = await conn.fetchrow(
                "SELECT * FROM issues WHERE id = $1 AND deleted_at IS NULL",
                issue_id
            )
            if not issue:
                raise NotFoundError("ไม่พบเรื่องนี้")

            # ตรวจว่าสังกัดระดับเดียวกับ current_level
            # - สำหรับระดับ room: ต้องเป็นสมาชิกห้องนั้น (หัวหน้าห้อง/รอง)
            # - สำหรับระดับ level/council: สังกัดระดับชั้น/สภา มองข้ามห้องได้
            # - ครูทั่วไป: รับเรื่องของระดับชั้นตัวเองได้ทุกระดับพีระมิด (เป็นผู้ดูแลระดับชั้น)
            in_room_role = await _user_role_in(conn, user_id, issue["room_id"])
            if in_room_role:
                level = ROLE_LEVEL.get(in_room_role, "student")
            else:
                # ไม่ใช่สมาชิกห้องนั้น — ดูระดับสูงสุดจากทุกตำแหน่ง (รองรับสภา/ประธานระดับ)
                level = await user_level(pool, user_id, room_id=None)

            can_accept_level = (level == issue["current_level"])
            if not can_accept_level:
                teacher_level = await _teacher_scope(conn, user_id)
                if teacher_level:
                    issue_room_level = await _room_level(conn, issue["room_id"])
                    can_accept_level = (issue_room_level == teacher_level)
                if not can_accept_level:
                    raise ForbiddenError("เรื่องนี้ไม่อยู่ในระดับของคุณ")

            # ตรวจว่ายังไม่มีคนรับ
            if issue["current_assignee_id"]:
                raise ValidationError("เรื่องนี้มีผู้รับอยู่แล้ว")

            now = datetime.now(timezone.utc)
            deadline = now + timedelta(days=estimated_days)

            await conn.execute(
                """
                UPDATE issues
                SET current_assignee_id = $1, status = 'in_progress', updated_at = NOW()
                WHERE id = $2
                """,
                user_id, issue_id
            )
            # role ของผู้รับ (ครูที่รับข้ามห้อง → ระบุเป็น role จริง/teacher)
            role = await _user_role_in(conn, user_id, issue["room_id"])
            if not role:
                role = await conn.fetchval(
                    """
                    SELECT class_role FROM students
                    WHERE user_id = $1 AND deleted_at IS NULL AND status = 'active'
                    ORDER BY id LIMIT 1
                    """,
                    user_id
                ) or "teacher"
            await conn.execute(
                "UPDATE issues SET current_assignee_role = $1 WHERE id = $2",
                role, issue_id
            )

            await conn.execute(
                """
                INSERT INTO issue_countdowns (issue_id, assignee_id, estimated_days, deadline)
                VALUES ($1, $2, $3, $4)
                """,
                issue_id, user_id, estimated_days, deadline
            )
            await conn.execute(
                """
                INSERT INTO issue_status_history (issue_id, status, changed_by, note)
                VALUES ($1, 'in_progress', $2, $3)
                """,
                issue_id, user_id, f"รับเรื่อง (ตั้งเวลา {estimated_days} วัน)"
            )


async def update_countdown(pool: asyncpg.Pool, user_id: int, issue_id: int, estimated_days: int) -> None:
    """แก้ไข countdown (ยืดเวลา) — ผู้รับเรื่อง หรือ admin/ครูที่จัดการเรื่องได้"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            cd = await conn.fetchrow(
                "SELECT id, issue_id FROM issue_countdowns WHERE issue_id = $1 AND assignee_id = $2 ORDER BY id DESC LIMIT 1",
                issue_id, user_id
            )
            if not cd:
                # ผู้รับเรื่องคนอื่น (admin/ครูระดับชั้นของเรื่อง) → แก้ countdown ล่าสุดได้
                issue = await conn.fetchrow(
                    "SELECT id FROM issues WHERE id = $1 AND deleted_at IS NULL",
                    issue_id
                )
                if not issue:
                    raise NotFoundError("ไม่พบเรื่องนี้")
                if not await _can_manage_issue(conn, user_id, issue):
                    raise NotFoundError("ไม่พบ countdown ของเรื่องนี้")
                cd = await conn.fetchrow(
                    "SELECT id FROM issue_countdowns WHERE issue_id = $1 ORDER BY id DESC LIMIT 1",
                    issue_id
                )
                if not cd:
                    raise NotFoundError("ไม่พบ countdown ของเรื่องนี้")

            now = datetime.now(timezone.utc)
            deadline = now + timedelta(days=estimated_days)
            await conn.execute(
                """
                UPDATE issue_countdowns
                SET estimated_days = $1, deadline = $2
                WHERE id = $3
                """,
                estimated_days, deadline, cd["id"]
            )


# ============================================================
# 🪜 ขั้นตอนการดำเนินงาน (Steps)
# ============================================================
async def add_step(pool: asyncpg.Pool, user_id: int, issue_id: int, step_title: str, step_detail: Optional[str] = None) -> int:
    """เพิ่มขั้นตอนการดำเนินงาน"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _ensure_assignee(conn, user_id, issue_id)
            step_order = await conn.fetchval(
                "SELECT COALESCE(MAX(step_order), 0) + 1 FROM issue_steps WHERE issue_id = $1",
                issue_id
            )
            return await conn.fetchval(
                """
                INSERT INTO issue_steps (issue_id, step_title, step_detail, step_order, created_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                issue_id, step_title, step_detail, step_order, user_id
            )


async def complete_step(pool: asyncpg.Pool, user_id: int, issue_id: int, step_id: int) -> None:
    """ทำขั้นตอนสำเร็จ"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _ensure_assignee(conn, user_id, issue_id)
            step = await conn.fetchrow(
                "SELECT id FROM issue_steps WHERE id = $1 AND issue_id = $2",
                step_id, issue_id
            )
            if not step:
                raise NotFoundError("ไม่พบขั้นตอนนี้")

            await conn.execute(
                """
                UPDATE issue_steps
                SET is_completed = TRUE, completed_at = NOW()
                WHERE id = $1
                """,
                step_id
            )


# ============================================================
# 🚀 Escalate (ส่งต่อไประดับบน) + Resolve
# ============================================================
async def escalate_issue(pool: asyncpg.Pool, user_id: int, issue_id: int, reason: Optional[str] = None) -> None:
    """ส่งต่อเรื่องไประดับบน (ถ้าเกินความสามารถ/ไม่ทันเวลา)"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            issue = await conn.fetchrow(
                "SELECT * FROM issues WHERE id = $1 AND deleted_at IS NULL",
                issue_id
            )
            if not issue:
                raise NotFoundError("ไม่พบเรื่องนี้")

            # ต้องเป็นผู้รับปัจจุบัน หรือ admin/ครูที่จัดการเรื่องนี้ได้
            if not await _can_manage_issue(conn, user_id, issue):
                raise ForbiddenError("เฉพาะผู้รับเรื่องหรือ admin ที่จะส่งต่อได้")

            next_level = NEXT_LEVEL.get(issue["current_level"])
            if not next_level:
                raise ValidationError("เรื่องนี้อยู่ระดับสูงสุดแล้ว (สภานักเรียน) — ส่งต่อไม่ได้")

            from_assignee = issue["current_assignee_id"]
            await conn.execute(
                """
                INSERT INTO issue_escalations (issue_id, from_level, to_level, from_assignee_id, reason)
                VALUES ($1, $2, $3, $4, $5)
                """,
                issue_id, issue["current_level"], next_level, from_assignee, reason
            )
            await conn.execute(
                """
                UPDATE issues
                SET current_level = $1, current_assignee_id = NULL, current_assignee_role = NULL,
                    status = 'escalated', updated_at = NOW()
                WHERE id = $2
                """,
                next_level, issue_id
            )
            await conn.execute(
                """
                INSERT INTO issue_status_history (issue_id, status, changed_by, note)
                VALUES ($1, 'escalated', $2, $3)
                """,
                issue_id, user_id, f"ส่งต่อไปยังระดับ {next_level}" + (f": {reason}" if reason else "")
            )


async def resolve_issue(pool: asyncpg.Pool, user_id: int, issue_id: int, note: Optional[str] = None) -> None:
    """ปิดเรื่อง (แก้ไขเสร็จ)"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            issue = await conn.fetchrow(
                "SELECT * FROM issues WHERE id = $1 AND deleted_at IS NULL",
                issue_id
            )
            if not issue:
                raise NotFoundError("ไม่พบเรื่องนี้")

            # ผู้รับปัจจุบัน หรือ admin/ครูที่จัดการเรื่องนี้ได้
            if not await _can_manage_issue(conn, user_id, issue):
                raise ForbiddenError("เฉพาะผู้รับเรื่องหรือ admin ที่จะปิดเรื่องได้")

            await conn.execute(
                """
                UPDATE issues
                SET status = 'resolved', resolved_at = NOW(), updated_at = NOW()
                WHERE id = $1
                """,
                issue_id
            )
            await conn.execute(
                """
                INSERT INTO issue_status_history (issue_id, status, changed_by, note)
                VALUES ($1, 'resolved', $2, $3)
                """,
                issue_id, user_id, note or "แก้ไขเสร็จสิ้น"
            )


async def cancel_issue(pool: asyncpg.Pool, user_id: int, issue_id: int, reason: Optional[str] = None) -> str:
    """
    ยกเลิก/ปัดตกเรื่อง
    - ผู้แจ้งกดยกเลิก → status='cancelled' (ถูกยกเลิก)
    - ผู้ดูแล (ผู้รับ/admin/ครูระดับชั้น) กดปัดตก → status='rejected' (ถูกปัดตก) — แยกหมวดจากผู้แจ้งยกเลิก
    คืน status ที่ตั้ง เพื่อให้ router ตอบกลับตรงกับสิ่งที่เกิดขึ้น
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            issue = await conn.fetchrow(
                "SELECT * FROM issues WHERE id = $1 AND deleted_at IS NULL",
                issue_id
            )
            if not issue:
                raise NotFoundError("ไม่พบเรื่องนี้")

            # ตรวจว่าเป็นผู้แจ้ง หรือผู้ดูแลเรื่องนี้ได้ (ผู้รับ/admin/ครูระดับชั้น)
            if issue["reporter_id"] != user_id and not await _can_manage_issue(conn, user_id, issue):
                raise ForbiddenError("เฉพาะผู้แจ้งหรือผู้ดูแลเรื่องนี้เท่านั้นที่ยกเลิก/ปัดตกได้")

            # ถ้าเรื่องเสร็จแล้ว/ปิดแล้ว ยกเลิกไม่ได้
            if issue["status"] in ("resolved",):
                raise ValidationError("เรื่องนี้ปิดไปแล้ว — ยกเลิกไม่ได้")

            # ผู้แจ้ง → ถูกยกเลิก, ผู้ดูแล → ถูกปัดตก
            if issue["reporter_id"] == user_id:
                new_status = "cancelled"
                default_note = "ผู้แจ้งยกเลิกเรื่อง"
            else:
                new_status = "rejected"
                default_note = "ถูกปัดตก"

            await conn.execute(
                """
                UPDATE issues
                SET status = $1, updated_at = NOW()
                WHERE id = $2
                """,
                new_status, issue_id
            )
            note = f"{default_note}" + (f": {reason}" if reason else "")
            await conn.execute(
                """
                INSERT INTO issue_status_history (issue_id, status, changed_by, note)
                VALUES ($1, $2, $3, $4)
                """,
                issue_id, new_status, user_id, note
            )
            return new_status


# ============================================================
# 🧩 Helpers
# ============================================================
async def _user_role_in(conn, user_id: int, room_id: int) -> Optional[str]:
    """หาตำแหน่งของ user ในห้อง"""
    return await conn.fetchval(
        """
        SELECT class_role FROM students
        WHERE user_id = $1 AND room_id = $2 AND deleted_at IS NULL AND status = 'active'
        """,
        user_id, room_id
    )


async def _student_display_name(conn, user_id: int, room_id: Optional[int]) -> Optional[str]:
    """ชื่อแสดงของ user: prefix+first_name+last_name จาก students (fallback users.full_name)
    — students บางแถว (เช่น register_user/self-signup) มี first/last name ว่าง แต่ full_name อยู่ที่ users"""
    row = await conn.fetchrow(
        """
        SELECT
            NULLIF(TRIM(CONCAT_WS(' ', s.prefix, s.first_name, s.last_name)), '') AS student_name,
            u.full_name
        FROM students s
        JOIN users u ON u.id = s.user_id
        WHERE s.user_id = $1
          AND s.room_id = COALESCE($2, s.room_id)
          AND s.deleted_at IS NULL AND s.status = 'active'
        ORDER BY s.id LIMIT 1
        """,
        user_id, room_id
    )
    if not row:
        return None
    return row["student_name"] or row["full_name"]


async def _is_involved(conn, user_id: int, issue_row) -> bool:
    """
    เช็คว่า user เกี่ยวข้องกับเรื่องนี้ไหม (เพื่อดูได้แม้ระดับต่ำกว่าปัจจุบัน):
    - เคยเป็นผู้รับ (จาก escalations.from_assignee_id หรือ countdown assignee)
    - อยู่ในห้องเดียวกับผู้แจ้ง (สมาชิกห้องนั้น เห็นเรื่องที่ออกจากห้องตัวเอง)
    """
    issue_id = issue_row["id"]

    # 1. เคยเป็นผู้รับมาก่อน (escalations / countdowns)
    prev = await conn.fetchval(
        """
        SELECT 1 FROM issue_escalations
        WHERE issue_id = $1 AND from_assignee_id = $2
        UNION ALL
        SELECT 1 FROM issue_countdowns
        WHERE issue_id = $1 AND assignee_id = $2
        LIMIT 1
        """,
        issue_id, user_id
    )
    if prev:
        return True

    # 2. อยู่ในห้องเดียวกับผู้แจ้ง (สำหรับเรื่องที่ยังระดับ room — สมาชิกห้องเห็นเรื่องของห้องตัวเอง)
    reporter_room = issue_row["reporter_room_id"] or issue_row["room_id"]
    if reporter_room:
        in_same_room = await conn.fetchval(
            """
            SELECT 1 FROM students
            WHERE user_id = $1 AND room_id = $2 AND deleted_at IS NULL AND status = 'active'
            """,
            user_id, reporter_room
        )
        if in_same_room:
            return True

    return False


async def _is_admin(conn, user_id: int) -> bool:
    """เช็คว่า user เป็น admin (ในห้องใดก็ได้) หรือ Super Admin"""
    if settings.SUPER_ADMIN_ID and int(user_id) == int(settings.SUPER_ADMIN_ID):
        return True
    row = await conn.fetchrow(
        "SELECT is_admin FROM students WHERE user_id = $1 AND deleted_at IS NULL AND status = 'active'",
        user_id
    )
    return bool(row and row["is_admin"])


async def _ensure_assignee(conn, user_id: int, issue_id: int) -> None:
    """ตรวจว่า user จัดการเรื่องนี้ได้ (ผู้รับปัจจุบัน / admin / ครูระดับชั้นของเรื่อง)"""
    issue = await conn.fetchrow(
        "SELECT current_assignee_id FROM issues WHERE id = $1 AND deleted_at IS NULL",
        issue_id
    )
    if not issue:
        raise NotFoundError("ไม่พบเรื่องนี้")
    if not await _can_manage_issue(conn, user_id, issue):
        raise ForbiddenError("เฉพาะผู้รับเรื่องเท่านั้นที่จัดการขั้นตอนนี้ได้")


# ============================================================
# 💬 คอมเมนต์ (แบบ YouTube) — เพิ่ม/แก้/ลบของตัวเอง
# ============================================================
async def add_comment(pool: asyncpg.Pool, user_id: int, issue_id: int, body: str) -> int:
    """เพิ่มคอมเมนต์ — ต้องมองเห็นเรื่องได้ (visibility เดียวกับ get_issue)
    ชื่อจริง/ห้องของผู้เขียนเป็น snapshot ตอนสร้าง (เสมอ แม้เรื่อง anonymous)"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            issue = await conn.fetchrow(
                "SELECT * FROM issues WHERE id = $1 AND deleted_at IS NULL",
                issue_id
            )
            if not issue:
                raise NotFoundError("ไม่พบเรื่องนี้")
            await _assert_can_view(conn, pool, user_id, issue)

            # snapshot ชื่อจริง/ห้องของผู้เขียน (ใช้ primary row ถ้ามีหลายห้อง)
            c = await conn.fetchrow(
                """
                SELECT
                    NULLIF(TRIM(CONCAT_WS(' ', s.prefix, s.first_name, s.last_name)), '') AS student_name,
                    u.full_name,
                    r.room_name
                FROM students s
                JOIN users u ON u.id = s.user_id
                LEFT JOIN rooms r ON r.id = s.room_id
                WHERE s.user_id = $1 AND s.deleted_at IS NULL AND s.status = 'active'
                ORDER BY s.id LIMIT 1
                """,
                user_id
            )
            commenter_name = (c["student_name"] or c["full_name"]) if c else None
            commenter_room = c["room_name"] if c else None

            comment_id = await conn.fetchval(
                """
                INSERT INTO issue_comments (issue_id, user_id, commenter_name, commenter_room, body)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                issue_id, user_id,
                commenter_name, commenter_room,
                body
            )

            from core.logger import AuditLogger
            await AuditLogger("issue_service").log(
                conn=conn, action="CREATE_COMMENT",
                actor_identifier=str(user_id), client_source="web",
                room_id=issue["room_id"], user_id=user_id,
                entity_type="issue_comment", entity_id=comment_id,
                new_values={"body": body},
            )
            return comment_id


async def _get_own_comment(conn, user_id: int, issue_id: int, comment_id: int):
    """ดึงคอมเมนต์ที่ยังไม่ถูกลบ + ตรวจว่าเป็นของ user เอง (แก้/ลบได้เฉพาะของตัวเอง)"""
    comment = await conn.fetchrow(
        """
        SELECT * FROM issue_comments
        WHERE id = $1 AND issue_id = $2 AND deleted_at IS NULL
        """,
        comment_id, issue_id
    )
    if not comment:
        raise NotFoundError("ไม่พบคอมเมนต์นี้")
    if comment["user_id"] != user_id:
        raise ForbiddenError("เฉพาะผู้เขียนคอมเมนต์เท่านั้นที่แก้ไข/ลบได้")
    return comment


async def update_comment(
    pool: asyncpg.Pool, user_id: int, issue_id: int, comment_id: int, body: str
) -> None:
    """แก้คอมเมนต์ของตัวเอง"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            issue = await conn.fetchrow(
                "SELECT * FROM issues WHERE id = $1 AND deleted_at IS NULL",
                issue_id
            )
            if not issue:
                raise NotFoundError("ไม่พบเรื่องนี้")
            await _assert_can_view(conn, pool, user_id, issue)
            comment = await _get_own_comment(conn, user_id, issue_id, comment_id)

            await conn.execute(
                "UPDATE issue_comments SET body = $1, updated_at = NOW() WHERE id = $2",
                body, comment_id
            )

            from core.logger import AuditLogger
            await AuditLogger("issue_service").log(
                conn=conn, action="UPDATE_COMMENT",
                actor_identifier=str(user_id), client_source="web",
                room_id=issue["room_id"], user_id=user_id,
                entity_type="issue_comment", entity_id=comment_id,
                old_values={"body": comment["body"]},
                new_values={"body": body},
            )


async def delete_comment(
    pool: asyncpg.Pool, user_id: int, issue_id: int, comment_id: int
) -> None:
    """soft delete คอมเมนต์ของตัวเอง (row ยังอยู่ deleted_at = NOW())"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            issue = await conn.fetchrow(
                "SELECT * FROM issues WHERE id = $1 AND deleted_at IS NULL",
                issue_id
            )
            if not issue:
                raise NotFoundError("ไม่พบเรื่องนี้")
            await _assert_can_view(conn, pool, user_id, issue)
            comment = await _get_own_comment(conn, user_id, issue_id, comment_id)

            deleted_id = await conn.fetchval(
                """
                UPDATE issue_comments
                SET deleted_at = NOW()
                WHERE id = $1 AND issue_id = $2 AND deleted_at IS NULL
                RETURNING id
                """,
                comment_id, issue_id
            )
            if deleted_id is None:
                raise NotFoundError("ไม่พบคอมเมนต์นี้")

            from core.logger import AuditLogger
            await AuditLogger("issue_service").log(
                conn=conn, action="DELETE_COMMENT",
                actor_identifier=str(user_id), client_source="web",
                room_id=issue["room_id"], user_id=user_id,
                entity_type="issue_comment", entity_id=comment_id,
                old_values={"body": comment["body"], "commenter_name": comment["commenter_name"]},
            )


async def get_comment(pool: asyncpg.Pool, user_id: int, issue_id: int, comment_id: int) -> dict:
    """ดึงคอมเมนต์เดี่ยว (ตรวจ visibility + ยังไม่ถูกลบ) สำหรับตอบ API"""
    async with pool.acquire() as conn:
        issue = await conn.fetchrow(
            "SELECT * FROM issues WHERE id = $1 AND deleted_at IS NULL",
            issue_id
        )
        if not issue:
            raise NotFoundError("ไม่พบเรื่องนี้")
        await _assert_can_view(conn, pool, user_id, issue)
        row = await conn.fetchrow(
            """
            SELECT * FROM issue_comments
            WHERE id = $1 AND issue_id = $2 AND deleted_at IS NULL
            """,
            comment_id, issue_id
        )
        if not row:
            raise NotFoundError("ไม่พบคอมเมนต์นี้")
        return _comment_to_dict(row)


# ============================================================
# 🔄 แปลงผลลัพธ์
# ============================================================
def _step_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "step_title": row["step_title"],
        "step_detail": row["step_detail"],
        "step_order": row["step_order"],
        "is_completed": row["is_completed"],
        "completed_at": row["completed_at"],
    }


def _countdown_to_dict(row) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": row["id"],
        "estimated_days": row["estimated_days"],
        "started_at": row["started_at"],
        "deadline": row["deadline"],
        "is_overdue": bool(row["deadline"] < now),
    }


def _esc_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "from_level": row["from_level"],
        "to_level": row["to_level"],
        "reason": row["reason"],
        "created_at": row["created_at"],
    }


def _history_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "status": row["status"],
        "note": row["note"],
        "created_at": row["created_at"],
    }


def _comment_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "commenter_name": row["commenter_name"],
        "commenter_room": row["commenter_room"],
        "body": row["body"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
