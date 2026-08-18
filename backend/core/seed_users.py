"""
Seed Users — สร้างบัญชีผู้ดูแลระบบอัตโนมัติตอนเปิดระบบครั้งแรก
==============================================================
สร้างบัญชี admin / ครูสภา / ประธานสภา ด้วย username ที่เดายาก + รหัสผ่านชั่วคราว
และตั้ง flag `must_change_password = TRUE` เพื่อบังคับให้เปลี่ยนรหัสตอน login ครั้งแรก

Idempotent: ถ้ามีผู้ใช้ในบทบาทเหล่านี้อยู่แล้ว (เช่น นำเข้า Excel / seed ไปแล้ว) → ข้าม
ข้อมูล username/rหัสชั่วคราวถูกพิมพ์ที่ log และเขียนลงไฟล์ (SEED_CREDENTIALS_FILE)
"""
import asyncio
import json
import logging
import os
import secrets
import string

import asyncpg

from core.config import settings
from core.rbac import get_role_permissions, get_role_is_admin
from services.auth_service import hash_password

logger = logging.getLogger("API_SEED_USERS")

# บทบาทที่จะ seed (ทุกตัวเป็น is_admin ตาม config/roles.json)
SEED_ROLES = [
    ("admin", "แอดมินระบบ", "แอดมิน", "ระบบ", "PADM"),     # สิทธิ์สูงสุด
    ("teacher_council", "ครูสภา", "ครู", "ที่ปรึกษาสภา", "TCH"),   # ดูแลทั้งโรงเรียน
    ("council_president", "ประธานสภา", "ประธาน", "สภานักเรียน", "PRS"),
]


def _random_username(prefix: str) -> str:
    """username เดายาก เช่น piri_admin_9f2k3c (ตัวพิมพ์เล็ก+hex — พิมพ์เองไม่พลาดง่าย)"""
    return f"piri_{prefix}_{secrets.token_hex(3)}"


def _random_password(length: int = 12) -> str:
    """รหัสผ่านชั่วคราวสุ่ม — ตัวพิมพ์ใหญ่/เล็ก/เลข/สัญลักษณ์"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_"
    # กันตัวอักษรที่พิมพ์/อ่านสับสน (0/O, 1/l/I) ในรหัสชั่วคราว
    safe = alphabet.replace("0", "").replace("O", "").replace("1", "").replace("l", "").replace("I", "")
    return "".join(secrets.choice(safe) for _ in range(length))


async def _has_privileged_users(pool: asyncpg.Pool) -> bool:
    """มี admin/ครูสภา/ประธานสภา อยู่แล้วหรือยัง (active) — ถ้ามีแล้วข้าม seed"""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT 1 FROM students
            WHERE class_role = ANY($1::text[])
              AND status = 'active'
              AND deleted_at IS NULL
            LIMIT 1
            """,
            [r[0] for r in SEED_ROLES],
        )


def _write_credentials_file(creds: dict) -> str:
    """เขียน username + รหัสชั่วคราวลงไฟล์ (gitignored) — path จาก settings"""
    lines = [
        "PIRIvoice — บัญชีผู้ดูแลระบบที่สร้างอัตโนมัติ (เปิดระบบครั้งแรก)",
        "=" * 60,
        "⚠️ ระบบจะบังคับให้เปลี่ยนรหัสผ่านเมื่อเข้าสู่ระบบครั้งแรก",
        "โปรดเก็บไฟล์นี้ไว้ในที่ปลอดภัย และลบออกหลังเปลี่ยนรหัสผ่านครบแล้ว",
        "",
    ]
    for role, info in creds.items():
        lines.append(f"[{role}] ({info['full_name']})")
        lines.append(f"  Username : {info['username']}")
        lines.append(f"  Password : {info['password']}")
        lines.append("")

    path = os.path.abspath(settings.SEED_CREDENTIALS_FILE)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


async def seed_default_users(pool: asyncpg.Pool) -> dict:
    """
    สร้างบัญชีผู้ดูแลระบบถ้ายังไม่มี (idempotent)
    คืน dict: { role: {username, password, full_name} } — ถ้าไม่ seed คืน {}
    """
    if await _has_privileged_users(pool):
        logger.info("ℹ️ พบบัญชี admin/ครูสภา/ประธานสภา อยู่แล้ว — ข้ามการ seed default users")
        return {}

    creds = {}
    async with pool.acquire() as conn:
        async with conn.transaction():
            for role, _label, first, last, code in SEED_ROLES:
                username = _random_username(role.replace("_", ""))
                password = _random_password()
                full_name = f"{first} {last}"
                student_id = f"{code}{secrets.token_hex(2).upper()}"  # ≤ 10 chars (VARCHAR(10))

                role_perms = get_role_permissions(role)
                role_is_admin = get_role_is_admin(role)

                # 1. users — login ด้วย username ยาว (เดายาก)
                user_id = await conn.fetchval(
                    """
                    INSERT INTO users (username, password_hash, full_name, must_change_password)
                    VALUES ($1, $2, $3, TRUE)
                    RETURNING id
                    """,
                    username, hash_password(password), full_name,
                )

                # 2. students — school-wide (room_id NULL) ตาม pattern admin/ครูสภา
                await conn.execute(
                    """
                    INSERT INTO students
                        (room_id, user_id, student_id, student_no, prefix,
                         first_name, last_name, class_role, staff_level, is_admin, permissions, status)
                    VALUES (NULL, $1, $2, 0, '', $3, $4, $5, NULL, $6, $7, 'active')
                    """,
                    user_id, student_id, first, last, role,
                    role_is_admin, json.dumps(role_perms),
                )

                creds[role] = {
                    "username": username,
                    "password": password,
                    "full_name": full_name,
                }

    # เขียนไฟล์ + log (นอก transaction — ไฟล์ไม่เกี่ยวกับ DB)
    path = _write_credentials_file(creds)
    logger.info(
        "✅ สร้างบัญชีผู้ดูแลระบบเริ่มต้นแล้ว (%d บัญชี) — เปลี่ยนรหัสผ่านเมื่อ login ครั้งแรก\n"
        "   เก็บข้อมูลไว้ในไฟล์: %s",
        len(creds), path,
    )
    for role, info in creds.items():
        logger.info("   • [%s] username=%s password=%s", role, info["username"], info["password"])

    return creds


if __name__ == "__main__":
    async def _main():
        p = await asyncpg.create_pool(settings.DATABASE_URL, min_size=1, max_size=2)
        try:
            await seed_default_users(p)
        finally:
            await p.close()
    asyncio.run(_main())
