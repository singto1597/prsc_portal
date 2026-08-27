import json
import asyncpg
from typing import Optional

from core.exceptions import NotFoundError, ValidationError, ConflictError
from core.rbac import get_role_permissions, get_role_is_admin
from services import auth_service

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
            room_id = await conn.fetchval(
                """
                INSERT INTO rooms (room_code, room_name, level, room_number)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                room_code, room_name, level, room_number
            )
            # 🛡️ Audit log (ทุก create ต้องบันทึก — ตามกฎ backend.md)
            from core.logger import AuditLogger
            await AuditLogger("student_service").log(
                conn=conn, action="CREATE_ROOM",
                actor_identifier="system", client_source="system",
                entity_type="room", entity_id=room_id,
                new_values={
                    "room_code": room_code, "room_name": room_name,
                    "level": level, "room_number": room_number,
                },
                endpoint_or_command="create_room",
            )
            return room_id


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

            # 🛡️ Audit log (ทุก UPDATE ต้องบันทึกใน transaction เดียวกัน)
            from core.logger import AuditLogger
            await AuditLogger("student_service").log(
                conn=conn, action="UPDATE_PROFILE",
                actor_identifier=str(user_id), client_source="web",
                user_id=user_id, entity_type="user", entity_id=user_id,
                old_values={
                    "prefix": old["prefix"], "first_name": old["first_name"],
                    "last_name": old["last_name"], "nickname": old["nickname"],
                    "phone_number": None, "email": None,
                },
                new_values={
                    "prefix": new_prefix, "first_name": new_first,
                    "last_name": new_last, "nickname": new_nick,
                    "phone_number": phone_number, "email": email,
                },
                endpoint_or_command="PATCH /students/me/profile",
            )

