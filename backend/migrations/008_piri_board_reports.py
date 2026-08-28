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
    # ⚠️ ใช้แบบ aggregate+JOIN (อ่านตารางลูกผ่านเดียว + GROUP BY) — ห้ามใช้ correlated subquery:
    # rehearsal บนข้อมูลระดับ prod (5k boards/100k comments/20k choices/200k votes) พบ
    # correlated subquery ช้า 100 เท่า (vote_count ~142s → lock piri_vote_choices ค้าง 2.4 นาที
    # ระหว่าง deploy จริง) ส่วนแบบ aggregate+JOIN ใช้เวลา <1s
    await conn.execute("""
        UPDATE piri_boards b
        SET comment_count = COALESCE(cnt.c, 0), updated_at = NOW()
        FROM (
            SELECT pb.id AS bid, agg.c
            FROM piri_boards pb
            LEFT JOIN (
                SELECT board_id, COUNT(*) AS c
                FROM piri_board_comments
                WHERE deleted_at IS NULL AND is_hidden_by_admin = FALSE
                GROUP BY board_id
            ) agg ON agg.board_id = pb.id
        ) cnt
        WHERE cnt.bid = b.id
    """)
    await conn.execute("""
        UPDATE piri_vote_choices vc
        SET vote_count = COALESCE(cnt.c, 0), updated_at = NOW()
        FROM (
            SELECT vc2.id AS cid, agg.c
            FROM piri_vote_choices vc2
            LEFT JOIN (
                SELECT choice_id, COUNT(*) AS c
                FROM piri_votes
                WHERE deleted_at IS NULL
                GROUP BY choice_id
            ) agg ON agg.choice_id = vc2.id
        ) cnt
        WHERE cnt.cid = vc.id
    """)
