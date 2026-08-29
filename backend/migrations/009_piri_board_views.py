"""
Migration: 009 — PIRI Boards: Dedup view_count (กัน F5 ปั่นยอด)
================================================================
- piri_board_views (board_id, user_id, viewed_at) — PRIMARY KEY (board_id, user_id)
  ใช้ dedup "การเข้าชม" ต่อ user: นับ 1 ครั้งต่อระยะเวลา (VIEW_DEDUP_WINDOW) ต่อ board
  → นักเรียนกด F5/refresh รัวๆ ไม่ปั่น view_count บอร์ดตัวเอง (adversarial review จับว่า
  เดิมบวกแบบดิบทุก request ไม่มี dedup)
- ไม่มี soft-delete (row เป็นแค่ log ของ "เคยเห็นล่าสุด" — ลบได้เลยถ้าต้องล้าง)
"""
VERSION = "009_piri_board_views"
DESCRIPTION = "PIRI Boards: dedup view_count ต่อ user (กัน F5 ปั่นยอด)"


async def upgrade(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS piri_board_views (
            board_id INTEGER NOT NULL REFERENCES piri_boards(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            viewed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (board_id, user_id)
        )
    """)
