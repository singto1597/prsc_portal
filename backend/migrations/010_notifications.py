"""
Migration: 010 — ระบบแจ้งเตือน (Notifications) + unread badge + read-receipt
============================================================================
- notifications: 1 แถว = 1 เหตุการณ์ ต่อ 1 ผู้รับ (แจ้งภายใน transaction เดียวกับข้อมูลหลัก
  ลอกแบบ AuditLogger) — ใช้สร้าง unread badge ตามเมนู (group_type) + หน้าแจ้งเตือนกลาง
- read_at NULL = ยังไม่อ่าน → badge = COUNT(*) WHERE read_at IS NULL GROUP BY group_type
- ไม่มี soft-delete (notification เป็น event log ชั่วคราว — ล้างตามอ่าน/ลบทิ้งได้ถ้าต้อง)
"""
VERSION = "010_notifications"
DESCRIPTION = "ระบบแจ้งเตือน: notifications + unread badge (issue/board/report)"


async def upgrade(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            group_type VARCHAR(30) NOT NULL,
            type VARCHAR(30) NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            entity_type VARCHAR(30),
            entity_id INTEGER,
            board_id INTEGER,
            actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            actor_name TEXT,
            read_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_user_unread_group
            ON notifications(user_id, group_type) WHERE read_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_notifications_user_created
            ON notifications(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_notifications_board
            ON notifications(board_id) WHERE board_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_notifications_entity
            ON notifications(entity_type, entity_id);
    """)
