"""
Migration: 006 — Indexes สำหรับ audit_logs (ระบบเก็บทุก action อย่างละเอียด)
====================================================================
audit_logs โตเร็วขึ้นมากหลัง Phase 3 (บันทึก login ล้มเหลว + issue mutations +
read/GET ทุกครั้ง) — ต้องมี index สำหรับ:
- (action, created_at)   → กราฟ traffic (login ต่อวัน) + filter หน้า audit log
- (user_id)              → ดูประวัติของ user คนเดียว
- (entity_type, entity_id) → ดูประวัติของ entity หนึ่ง
- (created_at)           → กลุ่ม/เรียงตามเวลา

(ใช้ CREATE INDEX IF NOT EXISTS เพื่อ idempotent + รันซ้ำบน DB ใหม่ได้)
"""
VERSION = "006_audit_logs_indexes"
DESCRIPTION = "Indexes สำหรับ audit_logs (action/created_at/user/entity)"


async def upgrade(conn) -> None:
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_action_created ON audit_logs(action, created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)"
    )
