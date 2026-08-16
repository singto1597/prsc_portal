import json
import asyncpg
import openpyxl
from typing import Optional

from core.exceptions import NotFoundError, ValidationError, ConflictError
from core.rbac import get_role_permissions, get_role_is_admin
from services import auth_service
from core.config import settings

# 🧭 แผนที่ตำแหน่งภาษาไทย → role key (ตรงกับ config/roles.json)
ROLE_MAP = {
    "ประธานสภา": "council_president",
    "สภานักเรียน": "council_member",
    "ประธานระดับ": "level_president",
    "หัวหน้าห้อง": "class_president",
    "รองวิชาการ": "vice_academic",
    "รองวินัย": "vice_discipline",
    "รองกิจกรรม": "vice_activity",
    "รองปฏิคม": "vice_reception",
    "รอง": "vice_reception",  # fallback
    "ครูสภา": "teacher_council",
    "ครู": "teacher",
    "ครูทั่วไป": "teacher",
    "แอดมิน": "admin",
    "ผู้ดูแลระบบ": "admin",
    "นักเรียน": "student",
    "": "student",
}


def map_role_label(label: str) -> str:
    """แปลงตำแหน่งจากภาษาไทย (ใน Excel) → role key"""
    label = (label or "").strip()
    return ROLE_MAP.get(label, "student")


async def list_rooms(pool: asyncpg.Pool) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, room_code, room_name, level, room_number FROM rooms WHERE deleted_at IS NULL ORDER BY room_code"
        )
    return [dict(r) for r in rows]


async def create_room(pool: asyncpg.Pool, room_code: str, room_name: str, level: Optional[str] = None, room_number: Optional[int] = None) -> int:
    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchval(
                "SELECT id FROM rooms WHERE room_code = $1 AND deleted_at IS NULL",
                room_code
            )
            if existing:
                return existing
            return await conn.fetchval(
                """
                INSERT INTO rooms (room_code, room_name, level, room_number)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                room_code, room_name, level, room_number
            )


async def list_students(pool: asyncpg.Pool, room_id: Optional[int] = None, search: Optional[str] = None, level: Optional[str] = None, limit: int = 500) -> list:
    """
    รายชื่อนักเรียน/สมาชิก
    - level: กรองเฉพาะระดับชั้น (เช่น 'ม.4') — ใช้กับ ครูทั่วไป (teacher) ที่เห็นได้แค่ระดับตัวเอง
    - room_id: กรองเฉพาะห้อง
    """
    async with pool.acquire() as conn:
        where = ["s.deleted_at IS NULL"]
        params = []
        if level:
            params.append(level)
            where.append(f"r.level = ${len(params)}")
        if room_id:
            params.append(room_id)
            where.append(f"s.room_id = ${len(params)}")
        if search:
            params.append(f"%{search}%")
            where.append(f"(s.first_name ILIKE ${len(params)} OR s.last_name ILIKE ${len(params)} OR s.student_id ILIKE ${len(params)})")

        params.append(limit)
        sql = f"""
            SELECT
                s.id, s.room_id, s.student_id, s.student_no,
                s.prefix, s.first_name, s.last_name, s.nickname,
                s.class_role, s.staff_level, s.is_admin, s.permissions, s.status,
                r.room_code, r.room_name, r.level
            FROM students s
            JOIN rooms r ON r.id = s.room_id
            WHERE {' AND '.join(where)}
            ORDER BY r.room_code, s.student_no
            LIMIT ${len(params)}
        """
        rows = await conn.fetch(sql, *params)
    return [_student_to_dict(r) for r in rows]


def _student_to_dict(row) -> dict:
    perms = row["permissions"] or []
    if isinstance(perms, str):
        import json
        try:
            perms = json.loads(perms)
        except json.JSONDecodeError:
            perms = []
    return {
        "id": row["id"],
        "room_id": row["room_id"],
        "room_code": row["room_code"],
        "room_name": row["room_name"],
        "student_id": row["student_id"],
        "student_no": row["student_no"],
        "prefix": row["prefix"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "nickname": row["nickname"],
        "class_role": row["class_role"],
        "staff_level": row.get("staff_level"),
        "is_admin": row["is_admin"],
        "permissions": perms,
        "status": row["status"],
    }


async def update_student(pool: asyncpg.Pool, student_id: int, *, class_role: Optional[str] = None, status: Optional[str] = None, is_admin: Optional[bool] = None, staff_level: Optional[str] = None, actor_user_id: Optional[int] = None, client_source: str = "web") -> None:
    """
    แก้ไขนักเรียน/สมาชิก
    - เมื่อเปลี่ยน class_role → permissions + is_admin จะถูก recompute จาก config/roles.json เสมอ
    - ครูทั่วไป (teacher) ต้องมี staff_level (ระดับชั้นที่ดูแล) — ถ้าไม่ระบุ ดึงจากระดับชั้นของห้อง
    - บันทึก audit_logs ใน transaction เดียวกัน
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchrow(
                "SELECT id, room_id, class_role, status, is_admin, staff_level FROM students WHERE id = $1 AND deleted_at IS NULL",
                student_id
            )
            if not current:
                raise NotFoundError("ไม่พบนักเรียน")

            new_role = class_role if class_role is not None else current["class_role"]
            new_status = status if status is not None else current["status"]
            new_admin = is_admin if is_admin is not None else current["is_admin"]
            new_staff_level = staff_level if staff_level is not None else current["staff_level"]

            # เมื่อ role เปลี่ยน → permissions + is_admin ตาม config/roles.json เสมอ
            role_perms = get_role_permissions(new_role)
            if is_admin is None:
                new_admin = get_role_is_admin(new_role)

            # ครูทั่วไปต้องรู้ระดับชั้นที่ดูแล (ถ้าไม่ระบุ → ใช้ระดับชั้นของห้องตัวเอง)
            if new_role == "teacher" and not new_staff_level:
                new_staff_level = await conn.fetchval(
                    "SELECT level FROM rooms WHERE id = $1", current["room_id"]
                )

            await conn.execute(
                """
                UPDATE students
                SET class_role = $1, status = $2, is_admin = $3, staff_level = $4,
                    permissions = $5, updated_at = NOW()
                WHERE id = $6
                """,
                new_role, new_status, new_admin, new_staff_level,
                json.dumps(role_perms), student_id
            )

            # 🛡️ Audit log (กฎ: ทุก UPDATE ต้องบันทึกใน transaction เดียวกัน)
            from core.logger import AuditLogger
            await AuditLogger("student_service").log(
                conn=conn,
                action="UPDATE_STUDENT",
                actor_identifier=str(actor_user_id) if actor_user_id else "system",
                client_source=client_source,
                user_id=actor_user_id,
                entity_type="student",
                entity_id=student_id,
                old_values={
                    "class_role": current["class_role"],
                    "status": current["status"],
                    "is_admin": current["is_admin"],
                    "staff_level": current["staff_level"],
                },
                new_values={
                    "class_role": new_role,
                    "status": new_status,
                    "is_admin": new_admin,
                    "staff_level": new_staff_level,
                },
            )


# ============================================================
# 👤 โปรไฟล์ตัวเอง (My Profile)
# ============================================================
async def get_my_profile(pool: asyncpg.Pool, user_id: int) -> dict:
    """ดึงข้อมูลโปรไฟล์ตัวเอง (จาก students + users + room)"""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                s.id, s.student_id, s.student_no, s.prefix, s.first_name, s.last_name,
                s.nickname, s.class_role, s.staff_level, s.status, s.room_id,
                r.room_code, r.room_name, r.level,
                u.username, u.full_name, u.phone_number, u.email
            FROM students s
            JOIN users u ON u.id = s.user_id
            LEFT JOIN rooms r ON r.id = s.room_id
            WHERE s.user_id = $1 AND s.deleted_at IS NULL AND s.status = 'active'
            ORDER BY s.id LIMIT 1
            """,
            user_id
        )
    if not row:
        raise NotFoundError("ไม่พบโปรไฟล์ของคุณ — กรุณาติดต่อผู้ดูแล")

    return dict(row)


async def update_my_profile(pool: asyncpg.Pool, user_id: int, *, prefix=None, first_name=None, last_name=None, nickname=None, phone_number=None, email=None) -> None:
    """แก้ไขโปรไฟล์ตัวเอง (เฉพาะฟิลด์ที่ส่งมา)"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            # หา student ของ user
            student = await conn.fetchrow(
                """
                SELECT id FROM students
                WHERE user_id = $1 AND deleted_at IS NULL AND status = 'active'
                ORDER BY id LIMIT 1
                """,
                user_id
            )
            if not student:
                raise NotFoundError("ไม่พบโปรไฟล์ของคุณ")

            # เก็บค่าเดิม → ใหม่ สำหรับ audit
            old = await conn.fetchrow(
                "SELECT prefix, first_name, last_name, nickname FROM students WHERE id = $1",
                student["id"]
            )

            # ตั้งค่าใหม่ (เฉพาะที่ส่งมา)
            new_prefix = prefix if prefix is not None else old["prefix"]
            new_first = first_name if first_name is not None else old["first_name"]
            new_last = last_name if last_name is not None else old["last_name"]
            new_nick = nickname if nickname is not None else old["nickname"]

            await conn.execute(
                """
                UPDATE students
                SET prefix = $1, first_name = $2, last_name = $3, nickname = $4,
                    updated_at = NOW()
                WHERE id = $5
                """,
                new_prefix, new_first, new_last, new_nick, student["id"]
            )

            # อัปเดต users (full_name, phone, email)
            user_fields = []
            user_params = [user_id]
            if first_name is not None or last_name is not None:
                full_name = f"{new_prefix or ''} {new_first or ''} {new_last or ''}".strip()
                user_fields.append("full_name = $%d" % (len(user_params) + 1))
                user_params.append(full_name)
            if phone_number is not None:
                user_fields.append("phone_number = $%d" % (len(user_params) + 1))
                user_params.append(phone_number)
            if email is not None:
                user_fields.append("email = $%d" % (len(user_params) + 1))
                user_params.append(email)

            if user_fields:
                await conn.execute(
                    f"UPDATE users SET {', '.join(user_fields)}, updated_at = NOW() WHERE id = $1",
                    *user_params
                )


# ============================================================
# 🚀 Import จากไฟล์ Excel
# ============================================================
ALL_COLUMNS = [
    "รหัสนักเรียน", "ห้องเรียน", "เลขที่",
    "คำนำหน้า", "ชื่อ", "นามสกุล", "ชื่อเล่น", "ตำแหน่งในห้องเรียน",
]
REQUIRED_COLUMNS = {"รหัสนักเรียน", "ห้องเรียน", "เลขที่"}


async def import_students_from_excel(pool: asyncpg.Pool, file_bytes: bytes, default_password: str = "1234", allowed_level: Optional[str] = None, actor_user_id: Optional[int] = None, client_source: str = "web") -> dict:
    """
    อ่านไฟล์ Excel (.xlsx) และสร้าง users + students พร้อม room

    - allowed_level: ถ้ากำหนด (ครูทั่วไปนำเข้า) จะข้ามแถวที่ห้องอยู่นอกระดับชั้นนี้
    - ครูสภา/แอดมิน: ไม่ผูกห้องเฉพาะ (school-wide) — ระบุห้องได้แต่ไม่บังคับ
    - ครูทั่วไป (teacher): staff_level = ระดับชั้นของห้องในแถวนั้น
    - is_admin ตาม config/roles.json เสมอ
    """
    try:
        wb = openpyxl.load_workbook(io := __import__("io").BytesIO(file_bytes), data_only=True)
    except Exception as e:
        raise ValidationError(f"อ่านไฟล์ Excel ไม่สำเร็จ: {e}")

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValidationError("ไฟล์ว่างเปล่า")

    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    col_index = {}
    for name in REQUIRED_COLUMNS:
        if name not in header:
            raise ValidationError(f"ไม่พบคอลัมน์ '{name}' ในไฟล์ Excel (ต้องมี: {', '.join(sorted(REQUIRED_COLUMNS))})")
        col_index[name] = header.index(name)
        
    for name in ALL_COLUMNS:
        if name not in col_index and name in header:
            col_index[name] = header.index(name)

    def get(r, name):
        i = col_index.get(name)
        return r[i] if i is not None and i < len(r) else None

    total = 0
    imported = 0
    skipped = 0
    errors = []
    
    # 🌟 สมุดจดจำ (Cache) สำหรับลดภาระฐานข้อมูลและป้องกัน Unique Error
    room_cache = {}
    user_cache = {}

    async with pool.acquire() as conn:
        async with conn.transaction():
            for r in rows[1:]:
                # ข้ามแถวว่าง
                if all(c is None or str(c).strip() == "" for c in r):
                    continue
                total += 1

                try:
                    student_id = str(get(r, "รหัสนักเรียน")).strip()
                    room_code = str(get(r, "ห้องเรียน")).strip()
                    student_no = int(get(r, "เลขที่") or 0)
                    prefix = str(get(r, "คำนำหน้า") or "").strip() or None
                    first_name = str(get(r, "ชื่อ") or "").strip()
                    last_name = str(get(r, "นามสกุล") or "").strip()
                    nickname = str(get(r, "ชื่อเล่น") or "").strip() or None
                    role_label = str(get(r, "ตำแหน่งในห้องเรียน") or "").strip()
                    class_role = map_role_label(role_label)
                    role_perms = get_role_permissions(class_role)
                    role_is_admin = get_role_is_admin(class_role)

                    if not student_id:
                        skipped += 1
                        errors.append(f"แถว {total}: ไม่มีรหัสนักเรียน")
                        continue
                    if not first_name and not last_name:
                        skipped += 1
                        errors.append(f"แถว {total}: ไม่มีชื่อ-นามสกุล")
                        continue

                    # 🌟 1. ระบบจัดการ Room (เช็คจาก Cache ก่อนเสมอ)
                    #    admin/ครูสภา ไม่ผูกห้องเฉพาะ (school-wide) — ระบุห้องได้แต่ไม่บังคับ
                    school_wide = class_role in ("admin", "teacher_council")
                    room_id = None
                    room_level = None
                    if room_code:
                        if room_code in room_cache:
                            room_id = room_cache[room_code]
                            room_level = await conn.fetchval(
                                "SELECT level FROM rooms WHERE id = $1", room_id
                            )
                        else:
                            room_id = await conn.fetchval(
                                "SELECT id FROM rooms WHERE room_code = $1 AND deleted_at IS NULL", room_code
                            )
                            if not room_id:
                                level = room_code.split("/")[0] if "/" in room_code else room_code
                                room_name = room_code
                                room_id = await conn.fetchval(
                                    """
                                    INSERT INTO rooms (room_code, room_name, level, room_number)
                                    VALUES ($1, $2, $3, NULL)
                                    RETURNING id
                                    """,
                                    room_code, room_name, level
                                )
                            room_level = await conn.fetchval(
                                "SELECT level FROM rooms WHERE id = $1", room_id
                            )
                            room_cache[room_code] = room_id  # บันทึกลงสมุดจด

                    # 🛡️ scope: ครูทั่วไปนำเข้าได้เฉพาะระดับชั้นตัวเอง
                    if allowed_level and not school_wide and room_level != allowed_level:
                        skipped += 1
                        errors.append(f"แถว {total}: ระดับชั้น {room_level or '-'} ไม่ตรงกับสิทธิ์ของคุณ ({allowed_level})")
                        continue

                    # ครูทั่วไป → staff_level = ระดับชั้นของห้องในแถวนั้น
                    staff_level = room_level if class_role == "teacher" else None

                    username = student_id

                    # 🌟 2. ระบบจัดการ User (เช็คจาก Cache ก่อนเสมอ)
                    if username in user_cache:
                        user = user_cache[username]
                    else:
                        user = await conn.fetchval(
                            "SELECT id FROM users WHERE username = $1 AND deleted_at IS NULL", username
                        )
                        if not user:
                            initial_password = student_id if default_password in ("", "1234") else default_password
                            hashed = auth_service.hash_password(initial_password)
                            user = await conn.fetchval(
                                """
                                INSERT INTO users (username, password_hash, full_name)
                                VALUES ($1, $2, $3)
                                RETURNING id
                                """,
                                username, hashed, f"{prefix} {first_name} {last_name}".strip()
                            )
                        user_cache[username] = user # บันทึกลงสมุดจด

                    # 3. สร้าง/อัปเดตข้อมูลนักเรียน (room_id อาจเป็น None สำหรับ admin/ครูสภา)
                    if room_id is not None:
                        student = await conn.fetchval(
                            """
                            SELECT id FROM students
                            WHERE room_id = $1 AND student_id = $2 AND deleted_at IS NULL
                            """,
                            room_id, student_id
                        )
                    else:
                        student = await conn.fetchval(
                            """
                            SELECT id FROM students
                            WHERE room_id IS NULL AND student_id = $1 AND deleted_at IS NULL
                            """,
                            student_id
                        )

                    if student:
                        await conn.execute(
                            """
                            UPDATE students
                            SET user_id = $1, student_no = $2, prefix = $3,
                                first_name = $4, last_name = $5, nickname = $6,
                                class_role = $7, staff_level = $8, is_admin = $9,
                                permissions = $10, updated_at = NOW()
                            WHERE id = $11
                            """,
                            user, student_no, prefix, first_name, last_name, nickname,
                            class_role, staff_level, role_is_admin, json.dumps(role_perms), student
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO students
                                (room_id, user_id, student_id, student_no, prefix,
                                 first_name, last_name, nickname, class_role, staff_level,
                                 is_admin, permissions)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                            """,
                            room_id, user, student_id, student_no, prefix, first_name, last_name,
                            nickname, class_role, staff_level, role_is_admin, json.dumps(role_perms)
                        )

                    imported += 1
                except (ValueError, TypeError) as e:
                    skipped += 1
                    errors.append(f"แถว {total}: ข้อมูลผิดรูปแบบ ({e})")

            # 🛡️ Audit log (กฎ: ทุก create/update ต้องบันทึกใน transaction เดียวกัน)
            from core.logger import AuditLogger
            await AuditLogger("student_service").log(
                conn=conn,
                action="IMPORT_STUDENTS",
                actor_identifier=str(actor_user_id) if actor_user_id else "system",
                client_source=client_source,
                user_id=actor_user_id,
                entity_type="student_batch",
                entity_id=None,
                status="success" if not errors else "partial",
                error_detail=None if not errors else "; ".join(errors[:20]),
                new_values={"total_rows": total, "imported": imported, "skipped": skipped},
            )

    return {
        "total_rows": total,
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:50],
    }