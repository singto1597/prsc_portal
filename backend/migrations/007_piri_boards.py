"""
Migration: 007 — PIRI Boards (ระบบสาธารณะ: PIRI Talk + PIRI Vote)
====================================================================
- เพิ่มคอลัมน์ปลายทางใน `issues`: requested_destination ('normal'/'vote'/'talk')
  + published_board_id (ชี้ piri_boards.id หลังสภาอนุมัติ — Phase 2 ตั้งค่า)
- สร้างตาราง 5 ตารางสำหรับฟีเจอร์ PIRI Boards:
  * piri_boards          — โพสต์สาธารณะ (ต้นเรื่องจาก issue ที่ขอ vote/talk)
  * piri_board_comments  — คอมเมนต์แบบ threaded (parent_comment_id = self-ref)
  * piri_vote_choices    — ตัวเลือกของ board แบบ vote
  * piri_votes           — เสียงโหวต (UNIQUE(board_id, user_id))
  * piri_board_reactions — react ต่อ board/comment (UNIQUE(target_type, target_id, user_id))

ทุกตารางมี created_at / updated_at / deleted_at TIMESTAMPTZ (soft delete บังคับ)
UNIQUE สองจุดเป็น partial unique index (WHERE deleted_at IS NULL) — soft delete
แล้วกลับมาโหวต/react ใหม่ได้ (pattern เดียวกับ uq_students_room_student_active)

ใช้ CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS + CREATE INDEX IF NOT EXISTS
เพื่อให้ idempotent และรองรับกรณี init_db สร้างไว้แล้วบน DB ใหม่ (รันซ้ำได้ปลอดภัย)
"""
VERSION = "007_piri_boards"
DESCRIPTION = "PIRI Boards: issues ปลายทาง + ตาราง boards/comments/votes/reactions"


async def upgrade(conn) -> None:
    # 1) issues — เพิ่มคอลัมน์ปลายทาง (ADD COLUMN IF NOT EXISTS = รันซ้ำปลอดภัย)
    await conn.execute("""
        ALTER TABLE issues
            ADD COLUMN IF NOT EXISTS requested_destination VARCHAR(20) NOT NULL DEFAULT 'normal'
    """)
    await conn.execute("""
        ALTER TABLE issues
            ADD COLUMN IF NOT EXISTS published_board_id INTEGER
    """)

    # 2) piri_boards — โพสต์สาธารณะ (source_issue_id → issues; author_id → ผู้สร้างต้นเรื่อง)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS piri_boards (
            id SERIAL PRIMARY KEY,
            source_issue_id INTEGER REFERENCES issues(id) ON DELETE SET NULL,
            board_type VARCHAR(10) NOT NULL DEFAULT 'talk',
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            cover_image_url TEXT,
            author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
            approved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            approved_at TIMESTAMP WITH TIME ZONE,
            view_count INTEGER NOT NULL DEFAULT 0,
            comment_count INTEGER NOT NULL DEFAULT 0,
            share_count INTEGER NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            allow_comments BOOLEAN NOT NULL DEFAULT TRUE,
            tags JSONB NOT NULL DEFAULT '[]'::jsonb,
            closed_at TIMESTAMP WITH TIME ZONE,
            closed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            close_reason TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT chk_piri_boards_type CHECK (board_type IN ('talk', 'vote')),
            CONSTRAINT chk_piri_boards_status CHECK (status IN ('active', 'closed', 'hidden'))
        )
    """)

    # 3) piri_board_comments — คอมเมนต์ + reply (self-referencing FK)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS piri_board_comments (
            id SERIAL PRIMARY KEY,
            board_id INTEGER NOT NULL REFERENCES piri_boards(id) ON DELETE CASCADE,
            parent_comment_id INTEGER REFERENCES piri_board_comments(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            body TEXT NOT NULL,
            image_url TEXT,
            is_edited BOOLEAN NOT NULL DEFAULT FALSE,
            edit_history JSONB NOT NULL DEFAULT '[]'::jsonb,
            ip_address VARCHAR(45),
            user_agent TEXT,
            is_hidden_by_admin BOOLEAN NOT NULL DEFAULT FALSE,
            hidden_reason TEXT,
            hidden_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP WITH TIME ZONE
        )
    """)

    # 4) piri_vote_choices — ตัวเลือกของ board แบบ vote
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS piri_vote_choices (
            id SERIAL PRIMARY KEY,
            board_id INTEGER NOT NULL REFERENCES piri_boards(id) ON DELETE CASCADE,
            choice_text TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            vote_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP WITH TIME ZONE
        )
    """)

    # 5) piri_votes — เสียงโหวต (ผู้ใช้คนละ 1 เสียงต่อ board — partial unique)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS piri_votes (
            id SERIAL PRIMARY KEY,
            board_id INTEGER NOT NULL REFERENCES piri_boards(id) ON DELETE CASCADE,
            choice_id INTEGER NOT NULL REFERENCES piri_vote_choices(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP WITH TIME ZONE
        )
    """)

    # 6) piri_board_reactions — react ต่อ board/comment (polymorphic target)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS piri_board_reactions (
            id SERIAL PRIMARY KEY,
            target_type VARCHAR(10) NOT NULL,
            target_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reaction_type VARCHAR(20) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            deleted_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT chk_piri_reactions_target_type CHECK (target_type IN ('board', 'comment'))
        )
    """)

    # 7) Indexes — feed / lookup / unique (partial → soft delete แล้ว vote/react ใหม่ได้)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_piri_boards_status_created ON piri_boards(status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_piri_boards_source_issue ON piri_boards(source_issue_id);
        CREATE INDEX IF NOT EXISTS idx_piri_boards_author ON piri_boards(author_id);
        CREATE INDEX IF NOT EXISTS idx_piri_board_comments_board ON piri_board_comments(board_id);
        CREATE INDEX IF NOT EXISTS idx_piri_board_comments_parent ON piri_board_comments(parent_comment_id);
        CREATE INDEX IF NOT EXISTS idx_piri_board_comments_user ON piri_board_comments(user_id);
        CREATE INDEX IF NOT EXISTS idx_piri_vote_choices_board ON piri_vote_choices(board_id, sort_order);
        CREATE INDEX IF NOT EXISTS idx_piri_votes_board ON piri_votes(board_id);
        CREATE INDEX IF NOT EXISTS idx_piri_votes_choice ON piri_votes(choice_id);
        CREATE INDEX IF NOT EXISTS idx_piri_board_reactions_target ON piri_board_reactions(target_type, target_id);
        CREATE INDEX IF NOT EXISTS idx_piri_board_reactions_user ON piri_board_reactions(user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_piri_votes_board_user_active
            ON piri_votes(board_id, user_id)
            WHERE deleted_at IS NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_piri_board_reactions_target_user_active
            ON piri_board_reactions(target_type, target_id, user_id)
            WHERE deleted_at IS NULL;
    """)
