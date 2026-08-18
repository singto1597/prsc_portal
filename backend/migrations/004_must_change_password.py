"""
Migration: 004 — เพิ่มคอลัมน์ must_change_password
====================================================
- ใช้สำหรับบัญชีที่ระบบสร้างให้ (seed users: admin/ครูสภา/ประธานสภา)
- flag = TRUE → ตอน login ครั้งแรกต้องเปลี่ยนรหัสผ่านก่อนใช้งาน (ดู router/auth + frontend guard)
"""
VERSION = "004_must_change_password"
DESCRIPTION = "เพิ่มคอลัมน์ users.must_change_password — บังคับเปลี่ยนรหัสผ่านครั้งแรก"


async def upgrade(conn) -> None:
    await conn.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE"
    )
