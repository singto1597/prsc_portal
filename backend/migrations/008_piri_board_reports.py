"""
Migration: 008 — PIRI Boards: Report (แจ้งความไม่เหมาะสม) + Counter reconcile
==============================================================================
- สร้างตาราง piri_board_reports: นักเรียนทุกคนแจ้งคอมเมนต์ไม่เหมาะสม (กลั่นแกล้ง/คำหยาบ)
  → สภานักเรียน/แอดมินรอรับเรื่อง (ไม่ต้องอ่านทุกคอมเมนต์) แล้วจัดการ (ซ่อน/ปัดตก)
  * reason จำกัดหมวด (bullying/profanity/spam/privacy/other) — กันสแปมเหตุผลมั่ว
  * status: 'open' (รอจัดการ) / 'resolved' (ซ่อนคอมเมนต์แล้ว) / 'dismissed' (ปัดตก ไม่ซ่อน)
  * UNIQUE(reporter_id, comment_id) partial — user แจ้งคอมเมนต์เดิมซ้ำไม่ได้ (กันสแปมรายงาน)
- 🔧 Counter reconcile (บทเรียน Phase 3: denormalized counter เพิ่มอย่างเดียว):
  * piri_boards.comment_count ← นับคอมเมนต์จริงที่ยังแสดง (deleted_at NULL + ไม่ถูกซ่อน)
  * piri_vote_choices.vote_count ← นับโหวตจริงที่ยัง active (deleted_at NULL)
  ให้ค่าที่ drift ไปตั้งแต่ก่อนมี feature hide กลับมาตรงกับข้อมูลจริงก่อน

ใช้ CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS — idempotent รันซ้ำปลอดภัย
"""
VERSION = "008_piri_board_reports"
DESCRIPTION = "PIRI Boards: ตาราง report คอมเมนต์ + reconcile counter drift"


async def upgrade(conn) -> None:
    # 1) piri_board_reports — รายงานคอมเมนต์ไม่เหมาะสม (รอสภา/แอดมินจัดการ)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS piri_board_reports (
            id SERIAL PRIMARY KEY,
            board_id INTEGER NOT NULL REFERENCES piri_boards(id) ON DELETE CASCADE,
            comment_id INTEGER NOT NULL REFERENCES piri_board_comments(id) ON DELETE CASCADE,
            reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reason VARCHAR(30) NOT NULL,
            detail TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            resolved_at TIMESTAMP WITH TIME ZONE,
            resolution_note TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT chk_piri_report_reason CHECK (reason IN ('bullying', 'profanity', 'spam', 'privacy', 'other')),
            CONSTRAINT chk_piri_report_status CHECK (status IN ('open', 'resolved', 'dismissed'))
        )
    """)

    # 2) Indexes — คิวรายงาน (กรอง status), ค้นจาก board/comment/reporter
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_piri_board_reports_status ON piri_board_reports(status);
        CREATE INDEX IF NOT EXISTS idx_piri_board_reports_board ON piri_board_reports(board_id);
        CREATE INDEX IF NOT EXISTS idx_piri_board_reports_comment ON piri_board_reports(comment_id);
        CREATE INDEX IF NOT EXISTS idx_piri_board_reports_reporter ON piri_board_reports(reporter_id);
        -- user แจ้งคอมเมนต์เดิมซ้ำไม่ได้ (partial: เฉพาะรายงานที่ยัง active) — กันสแปมรายงาน
        CREATE UNIQUE INDEX IF NOT EXISTS uq_piri_board_report_user_comment_active
            ON piri_board_reports(reporter_id, comment_id)
            WHERE deleted_at IS NULL;
    """)

    # 3) 🔧 Reconcile counter drift — ให้ comment_count/vote_count ตรงกับข้อมูลจริงก่อน feature hide
    await conn.execute("""
        UPDATE piri_boards b
        SET comment_count = (
                SELECT COUNT(*) FROM piri_board_comments c
                WHERE c.board_id = b.id
                  AND c.deleted_at IS NULL
                  AND c.is_hidden_by_admin = FALSE
            ),
            updated_at = NOW()
    """)
    await conn.execute("""
        UPDATE piri_vote_choices vc
        SET vote_count = (
                SELECT COUNT(*) FROM piri_votes v
                WHERE v.choice_id = vc.id AND v.deleted_at IS NULL
            ),
            updated_at = NOW()
    """)
