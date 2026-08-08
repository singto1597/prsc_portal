import json
import os
import asyncpg
from core.exceptions import ForbiddenError
from core.config import settings

# 💡 รายการสิทธิ์ทั้งหมดของระบบ PRSC Portal
# (ตำแหน่ง/ระดับ จะแมปกับ permissions ผ่าน config/roles.json)
AVAILABLE_PERMISSIONS = [
    "SUBMIT_ISSUE",          # นักเรียนทุกคนแจ้งปัญหา/ความคิดเห็นได้
    "VIEW_OWN_ISSUES",       # เห็นเฉพาะเรื่องของตัวเอง
    "RECEIVE_ISSUES",        # รับเรื่อง (หัวหน้าห้อง + รอง)
    "MANAGE_ISSUE_STEPS",    # เพิ่มขั้นตอนการดำเนินงาน
    "SET_COUNTDOWN",         # ตั้งเวลานับถอยหลังงาน
    "ESCALATE_ISSUE",        # ส่งต่อเรื่องไประดับบน
    "VIEW_LEVEL_PYRAMID",    # เห็นเรื่องของระดับล่างลงมา (มองลงเป็นพีระมิด)
    "MANAGE_STUDENTS",       # จัดการนักเรียน (import Excel)
    "VIEW_DASHBOARD",        # ดู dashboard/รายงาน
    "MANAGE_SETTINGS",       # ตั้งค่าระบบ
]

async def require_member(conn: asyncpg.Connection, room_id: int, user_id: int):
    """เช็คว่า user เป็นสมาชิก active ของห้อง/ระดับนี้หรือไม่ (กัน cross-level data leak)."""
    if settings.SUPER_ADMIN_ID and int(user_id) == int(settings.SUPER_ADMIN_ID):
        return True

    row = await conn.fetchval(
        "SELECT 1 FROM students WHERE room_id = $1 AND user_id = $2 AND status = 'active' AND deleted_at IS NULL",
        room_id, int(user_id)
    )
    if not row:
        raise ForbiddenError("คุณไม่ได้เป็นสมาชิกที่ใช้งานอยู่ในระดับนี้")

    return True

async def require_permission(conn: asyncpg.Connection, room_id: int, user_id: int, required_permission: str):
    """
    Granular RBAC (ระดับห้อง): SUPER_ADMIN_ID และ is_admin ผ่านฉลุย
    ไม่งั้นเช็คจาก JSONB array `permissions` บนตาราง students ของห้องนั้น
    """
    # 1. Super Admin (God Mode ระดับ Server)
    if settings.SUPER_ADMIN_ID and int(user_id) == int(settings.SUPER_ADMIN_ID):
        return True

    # 2. Query ค่า is_admin + permissions จากตาราง students
    row = await conn.fetchrow(
        """
        SELECT is_admin, permissions, status
        FROM students
        WHERE room_id = $1 AND user_id = $2 AND deleted_at IS NULL
        """,
        room_id, int(user_id)
    )

    if not row:
        raise ForbiddenError("Access Denied: ไม่พบข้อมูลของคุณในระดับนี้")

    if row['status'] != 'active':
        raise ForbiddenError("Access Denied: บัญชีของคุณในระดับนี้ยังไม่ได้รับการอนุมัติ หรือถูกระงับ")

    # 3. God Mode ของระดับ: is_admin ข้ามการเช็คสิทธิ์ย่อย
    if row['is_admin']:
        return True

    # 4. เช็คสิทธิ์ย่อยจาก permissions (JSONB array)
    user_permissions = _parse_permissions(row['permissions'])

    if required_permission not in user_permissions:
        raise ForbiddenError(f"Access Denied: คุณไม่มีสิทธิ์ '{required_permission}'")

    return True


async def require_permission_anywhere(conn: asyncpg.Connection, user_id: int, required_permission: str):
    """
    Granular RBAC (ข้ามทุกห้อง): เช็คว่า user มีสิทธิ์ permission ในห้อง/ตำแหน่งใดก็ได้
    ใช้สำหรับสิทธิ์ระดับโรงเรียน เช่น MANAGE_STUDENTS, VIEW_DASHBOARD, MANAGE_SETTINGS
    """
    # 1. Super Admin (God Mode ระดับ Server)
    if settings.SUPER_ADMIN_ID and int(user_id) == int(settings.SUPER_ADMIN_ID):
        return True

    # 2. ดึงทุก membership ที่ active ของ user
    rows = await conn.fetch(
        """
        SELECT is_admin, permissions, status
        FROM students
        WHERE user_id = $1 AND deleted_at IS NULL
        """,
        int(user_id)
    )

    if not rows:
        raise ForbiddenError("Access Denied: ไม่พบข้อมูลของคุณ")

    for row in rows:
        if row['status'] != 'active':
            continue
        # is_admin ผ่านฉลุย
        if row['is_admin']:
            return True
        perms = _parse_permissions(row['permissions'])
        if required_permission in perms:
            return True

    raise ForbiddenError(f"Access Denied: คุณไม่มีสิทธิ์ '{required_permission}'")


def _parse_permissions(raw_perms) -> list:
    """แปลง permissions JSONB → list (รองรับทั้ง str และ list จาก asyncpg)"""
    if not raw_perms:
        return []
    if isinstance(raw_perms, str):
        try:
            return json.loads(raw_perms)
        except json.JSONDecodeError:
            return []
    return list(raw_perms)


# 🧭 แคช permissions ตาม role (อ่านจาก config/roles.json ครั้งเดียว)
_ROLE_PERMS_CACHE = None


def get_role_permissions(role: str) -> list:
    """
    คืน list permissions ของ role (จาก config/roles.json)
    ใช้ตอน register/import/seed เพื่อให้ students.permissions มีค่าตามตำแหน่งจริง
    (ทำให้ frontend รู้ว่าซ่อน/โชว์เมนูไหน)
    """
    global _ROLE_PERMS_CACHE
    if _ROLE_PERMS_CACHE is None:
        roles_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "roles.json")
        try:
            with open(roles_path, encoding="utf-8") as f:
                data = json.load(f)
            _ROLE_PERMS_CACHE = data.get("roles", {})
        except Exception:
            _ROLE_PERMS_CACHE = {}

    role_data = _ROLE_PERMS_CACHE.get(role, {})
    return list(role_data.get("permissions", []))
