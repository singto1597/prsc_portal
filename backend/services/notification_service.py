"""
🔔 ระบบแจ้งเตือน (Notifications) — unread badge + read-receipt
=============================================================
- ทุก write ที่สำคัญจะ insert notification แถวใน transaction เดียวกับข้อมูลหลัก
  (ลอกแบบ AuditLogger — ตามกฎ backend.md) ผ่าน notify()/notify_bulk()/notify_fanout()
- group_type ใช้สร้าง badge ตามเมนู: issue_mine (เรื่องของฉัน) / issue_received (เรื่องที่รับ)
  / board (PIRI Boards) / report (จัดการรายงาน)
- read_at NULL = ยังไม่อ่าน → badge = COUNT(*) WHERE read_at IS NULL GROUP BY group_type
- เปิดหน้ารายละเอียด (เรื่อง/บอร์ด/รายงาน) → mark_read → badge ลดลง

ทุกฟังก์ชันรับ `conn` ที่อยู่ใน transaction ของ caller (ไม่เปิด transaction เอง)
"""
from typing import Iterable, List, Optional

from core.exceptions import ValidationError

# กลุ่ม badge ตามเมนู (เรียงตาม GROUP_TABS ใน frontend)
GROUP_TYPES = ("issue_mine", "issue_received", "board", "report")


# ============================================================
# ✍️ Write helpers — เรียกภายใน transaction ของ caller
# ============================================================

async def notify(
    conn,
    *,
    user_id: int,
    group_type: str,
    type: str,
    title: str,
    body: str,
    entity_type: str,
    entity_id: int,
    board_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    actor_name: Optional[str] = None,
) -> None:
    """สร้าง notification 1 แถว (skip ถ้า actor ทำกับตัวเอง — ไม่สแปมตัวเอง)"""
    if actor_id is not None and int(actor_id) == int(user_id):
        return
    await conn.execute(
        """
        INSERT INTO notifications
            (user_id, group_type, type, title, body, entity_type, entity_id,
             board_id, actor_id, actor_name)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        user_id, group_type, type, title, body, entity_type, entity_id,
        board_id, actor_id, actor_name,
    )


async def notify_bulk(
    conn,
    user_ids: Iterable[int],
    *,
    group_type: str,
    type: str,
    title: str,
    body: str,
    entity_type: str,
    entity_id: int,
    board_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    actor_name: Optional[str] = None,
) -> None:
    """หลายผู้รับในคราวเดียว (filter actor ออกก่อน insert)"""
    ids = [
        u for u in {int(x) for x in user_ids}
        if actor_id is None or int(u) != int(actor_id)
    ]
    if not ids:
        return
    await conn.executemany(
        """
        INSERT INTO notifications
            (user_id, group_type, type, title, body, entity_type, entity_id,
             board_id, actor_id, actor_name)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        [
            (uid, group_type, type, title, body, entity_type, entity_id,
             board_id, actor_id, actor_name)
            for uid in ids
        ],
    )


async def notify_fanout(
    conn,
    *,
    group_type: str,
    type: str,
    title: str,
    body: str,
    entity_type: str,
    entity_id: int,
    board_id: Optional[int] = None,
    actor_id: Optional[int] = None,
    actor_name: Optional[str] = None,
) -> None:
    """Fan-out ไปทุก active user (ตาราง students) — ขนาดโรงเรียนไม่กี่ร้อย/พันคน OK
    ใน transaction เดียว (ถ้า >10k คนค่อยย้ายไป queue ตามแผน)"""
    await conn.execute(
        """
        INSERT INTO notifications
            (user_id, group_type, type, title, body, entity_type, entity_id,
             board_id, actor_id, actor_name)
        SELECT DISTINCT user_id, $1::varchar, $2::varchar, $3::text, $4::text, $5::varchar,
               $6::int, $7::int, $8::int, $9::text
        FROM students
        WHERE deleted_at IS NULL AND status = 'active'
          AND ($8::int IS NULL OR user_id <> $8)
        """,
        group_type, type, title, body, entity_type, entity_id,
        board_id, actor_id, actor_name,
    )


# ============================================================
# 👥 Receiver helpers — ผู้รับตามระดับ (ใช้ภายใน transaction hook)
# ============================================================

async def _room_receiver_ids(conn, room_id: int) -> List[int]:
    """หัวหน้าห้อง + รอง 4 ฝ่าย ในห้องนั้น (ทุกคนถือ RECEIVE_ISSUES)"""
    rows = await conn.fetch(
        """
        SELECT user_id FROM students
        WHERE room_id = $1 AND deleted_at IS NULL AND status = 'active'
          AND class_role IN ('class_president','vice_academic','vice_discipline','vice_activity','vice_reception')
        """,
        room_id,
    )
    return [r["user_id"] for r in rows]


async def _council_ids(conn) -> List[int]:
    """สภานักเรียน/ประธานสภา/ครูสภา + admin (DISTINCT กันคนมีหลายห้อง)"""
    rows = await conn.fetch(
        """
        SELECT DISTINCT user_id FROM students
        WHERE deleted_at IS NULL AND status = 'active'
          AND (is_admin = TRUE OR class_role IN ('council_member','council_president','teacher_council'))
        """
    )
    return [r["user_id"] for r in rows]


async def _level_president_ids(conn, level: str) -> List[int]:
    """ประธานระดับของระดับชั้น (rooms.level = ระดับของเรื่อง)"""
    rows = await conn.fetch(
        """
        SELECT s.user_id FROM students s
        JOIN rooms r ON r.id = s.room_id
        WHERE s.class_role = 'level_president'
          AND s.deleted_at IS NULL AND s.status = 'active'
          AND r.level = $1 AND r.deleted_at IS NULL
        """,
        level,
    )
    return [r["user_id"] for r in rows]


async def _user_display_name(conn, user_id: int) -> Optional[str]:
    """ชื่อแสดง (prefix+first+last จาก students / fallback users.full_name)"""
    c = await conn.fetchrow(
        """
        SELECT NULLIF(TRIM(CONCAT_WS(' ', s.prefix, s.first_name, s.last_name)), '') AS student_name,
               u.full_name
        FROM students s
        JOIN users u ON u.id = s.user_id
        WHERE s.user_id = $1 AND s.deleted_at IS NULL AND s.status = 'active'
        ORDER BY s.id LIMIT 1
        """,
        user_id,
    )
    return (c["student_name"] or c["full_name"]) if c else None


def _mask_actor(reporter_name: Optional[str], is_anonymous: bool) -> Optional[str]:
    """ไม่รั่วชื่อผู้แจ้งถ้าเรื่องเป็น anonymous"""
    return "ไม่ระบุชื่อ" if is_anonymous else reporter_name


# ============================================================
# 📖 Read + mark-read
# ============================================================

async def get_unread_counts(pool, user_id: int) -> dict:
    """badge = unread notification ต่อกลุ่ม (index เร็ว, sub-ms)"""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT group_type, COUNT(*)::int AS cnt
            FROM notifications
            WHERE user_id = $1 AND read_at IS NULL
            GROUP BY group_type
            """,
            user_id,
        )
    counts = {r["group_type"]: r["cnt"] for r in rows}
    for g in GROUP_TYPES:
        counts.setdefault(g, 0)
    return {"counts": counts, "total": sum(counts.values())}


def _to_dict(r) -> dict:
    return {
        "id": r["id"],
        "group_type": r["group_type"],
        "type": r["type"],
        "title": r["title"],
        "body": r["body"],
        "entity_type": r["entity_type"],
        "entity_id": r["entity_id"],
        "board_id": r["board_id"],
        "actor_id": r["actor_id"],
        "actor_name": r["actor_name"],
        "read_at": r["read_at"],
        "created_at": r["created_at"],
    }


async def list_notifications(
    pool,
    user_id: int,
    *,
    group_type: Optional[str] = None,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """รายการแจ้งเตือนของฉัน (ล่าสุดก่อน) — envelope {items,total,page,page_size,pages}"""
    async with pool.acquire() as conn:
        where = ["user_id = $1"]
        params: list = [user_id]
        if group_type:
            params.append(group_type)
            where.append(f"group_type = ${len(params)}")
        if unread_only:
            where.append("read_at IS NULL")
        where_sql = " AND ".join(where)

        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM notifications WHERE {where_sql}", *params
        )
        rows = await conn.fetch(
            f"""
            SELECT * FROM notifications
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """,
            *params, limit, offset,
        )
    return {
        "items": [_to_dict(r) for r in rows],
        "total": total,
        "page": offset // limit + 1 if limit else 1,
        "page_size": limit,
        "pages": (total + limit - 1) // limit if limit and total else 0,
    }


async def mark_read(
    pool,
    user_id: int,
    *,
    ids: Optional[List[int]] = None,
    group_type: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    board_id: Optional[int] = None,
    all_: bool = False,
) -> int:
    """Mark อ่าน — ยืดหยุ่น: ids | group_type | entity_type(+entity_id) | board_id | read_all
    ⚠️ ถ้าไม่มี criteria เลยและไม่ใช่ read_all → 400 (กันเผลอเคลียร์ทุกอย่าง)"""
    if not all_ and not (ids or group_type or entity_type or entity_id is not None or board_id is not None):
        raise ValidationError("ระบุเงื่อนไขการอ่าน (ids/group_type/entity/board_id) หรือ read_all")

    async with pool.acquire() as conn:
        where = ["user_id = $1", "read_at IS NULL"]
        params: list = [user_id]
        if not all_:
            if ids:
                params.append(list(ids))
                where.append(f"id = ANY(${len(params)}::int[])")
            if group_type:
                params.append(group_type)
                where.append(f"group_type = ${len(params)}")
            if entity_type:
                params.append(entity_type)
                where.append(f"entity_type = ${len(params)}")
            if entity_id is not None:
                params.append(entity_id)
                where.append(f"entity_id = ${len(params)}")
            if board_id is not None:
                params.append(board_id)
                where.append(f"board_id = ${len(params)}")
        return await conn.fetchval(
            f"""
            WITH updated AS (
                UPDATE notifications SET read_at = NOW()
                WHERE {" AND ".join(where)}
                RETURNING id
            )
            SELECT COUNT(*) FROM updated
            """,
            *params,
        )
