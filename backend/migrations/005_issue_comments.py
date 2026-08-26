"""
Migration: 005 — ตารางคอมเมนต์ในเรื่อง (issue_comments)
====================================================================
เพิ่มตาราง `issue_comments` สำหรับฟีเจอร์คอมเมนต์แบบ YouTube:
- แสดงชื่อผู้คอมเมนต์ + เวลา + ข้อความ (ให้รู้ว่ามีคนรับทราบเรื่อง)
- user_id → users(id) ON DELETE SET NULL (ผู้ถูกลบ คอมเมนต์ยังอยู่ + ชื่อ snapshot)
- commenter_name/commenter_room เป็น snapshot ตอนสร้าง (แบบ reporter_name)
- deleted_at = soft delete (ลบของตัวเองได้ แต่ row ยังอยู่)

(ใช้ CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS เพื่อให้ idempotent
และรองรับกรณี init_db สร้างตารางนี้ไปแล้วใน DB ใหม่)
"""
VERSION = "005_issue_comments"
DESCRIPTION = "คอมเมนต์ในเรื่อง: ตาราง issue_comments + index"


async def upgrade(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS issue_comments (
            id SERIAL PRIMARY KEY,
            issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            commenter_name TEXT,
            commenter_room TEXT,
            body TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE,
            deleted_at TIMESTAMP
        )
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_issue_comments_issue ON issue_comments(issue_id)"
    )
