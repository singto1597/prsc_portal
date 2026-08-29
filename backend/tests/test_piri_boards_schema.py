"""
Schema Test: PIRI Boards (Phase 1 — Database Schema & Migrations)

ตรวจว่า init_db + migration 007 สร้างโครงสร้างตารางสาธารณะครบถ้วน:
- piri_boards / piri_board_comments / piri_vote_choices / piri_votes / piri_board_reactions
- issues ถูกเพิ่มคอลัมน์ requested_destination + published_board_id
- ทุกตารางใหม่มี created_at / updated_at / deleted_at TIMESTAMPTZ (soft delete บังคับ)
- UNIQUE(board_id, user_id) / UNIQUE(target_type, target_id, user_id) เป็น partial index

deep verification ผ่าน information_schema / pg_indexes (ไม่อ่านจาก service — ตรวจอิสระ)
"""
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest

from core.config import settings
from core.init_db import init_db

# ตารางที่ฟีเจอร์นี้สร้าง (ผ่าน init_db CREATE TABLE + migration 007)
PIRI_TABLES = [
    "piri_boards",
    "piri_board_comments",
    "piri_vote_choices",
    "piri_votes",
    "piri_board_reactions",
]


@pytest.mark.asyncio
async def test_fresh_db_has_all_piri_boards_tables(db_pool):
    """init_db บน DB ใหม่ → ต้องมีครบ 5 ตาราง + issues คอลัมน์ปลายทาง + soft-delete column"""
    async with db_pool.acquire() as conn:
        # 1. ตารางครบ 5 ตัว
        rows = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY($1::text[])
            """,
            PIRI_TABLES,
        )
        found = {r["table_name"] for r in rows}
        assert found == set(PIRI_TABLES), f"ตารางหาย: {set(PIRI_TABLES) - found}"

        # 2. ทุกตารางใหม่มี created_at/updated_at/deleted_at (TIMESTAMPTZ = soft delete)
        for table in PIRI_TABLES:
            cols = {
                r["column_name"]: r["data_type"]
                for r in await conn.fetch(
                    """
                    SELECT column_name, data_type FROM information_schema.columns
                    WHERE table_name = $1
                    """,
                    table,
                )
            }
            for required in ("created_at", "updated_at", "deleted_at"):
                assert cols.get(required) == "timestamp with time zone", (
                    f"{table}.{required} ต้องเป็น TIMESTAMPTZ (soft delete) — ได้ {cols.get(required)}"
                )

        # 3. issues ถูกเพิ่มคอลัมน์ปลายทาง
        issue_cols = {
            r["column_name"] for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'issues'"
            )
        }
        assert "requested_destination" in issue_cols, "issues.requested_destination ต้องมี"
        assert "published_board_id" in issue_cols, "issues.published_board_id ต้องมี"

        # 4. UNIQUE constraint (partial — WHERE deleted_at IS NULL) ถูกสร้าง
        idx = {
            r["indexname"]
            for r in await conn.fetch(
                "SELECT indexname FROM pg_indexes WHERE tablename = ANY($1::text[])",
                PIRI_TABLES,
            )
        }
        assert "uq_piri_votes_board_user_active" in idx, "UNIQUE(board_id, user_id) หาย"
        assert "uq_piri_board_reactions_target_user_active" in idx, (
            "UNIQUE(target_type, target_id, user_id) หาย"
        )


@pytest.mark.asyncio
async def test_partial_unique_blocks_duplicate_vote_but_allows_revote_after_soft_delete(db_pool):
    """partial unique index: ผู้ใช้โหวตซ้ำถูก block แต่ soft delete แล้วโหวตใหม่ได้"""
    async with db_pool.acquire() as conn:
        # สร้าง board (vote) + choice (จำเป็นต้องมี FK)
        board_id = await conn.fetchval(
            """
            INSERT INTO piri_boards (board_type, title, description)
            VALUES ('vote', 'board_a', 'desc')
            RETURNING id
            """
        )
        choice_id = await conn.fetchval(
            """
            INSERT INTO piri_vote_choices (board_id, choice_text)
            VALUES ($1, 'option_a')
            RETURNING id
            """,
            board_id,
        )
        # ต้องมี user จริง (FK users)
        user_id = await conn.fetchval(
            """
            INSERT INTO users (username, password_hash, full_name)
            VALUES ('schema_voter_1', 'x', 'Voter 1')
            RETURNING id
            """
        )

        # 2. โหวตครั้งแรก OK
        await conn.execute(
            """
            INSERT INTO piri_votes (board_id, choice_id, user_id)
            VALUES ($1, $2, $3)
            """,
            board_id, choice_id, user_id,
        )

        # 3. โหวตซ้ำ → UniqueViolation (UNIQUE(board_id, user_id))
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await conn.execute(
                """
                INSERT INTO piri_votes (board_id, choice_id, user_id)
                VALUES ($1, $2, $3)
                """,
                board_id, choice_id, user_id,
            )

        # 4. soft delete โหวตเดิม → โหวตใหม่ได้ (partial index ไม่ชน row ที่ลบแล้ว)
        await conn.execute(
            "UPDATE piri_votes SET deleted_at = NOW() WHERE board_id = $1 AND user_id = $2",
            board_id, user_id,
        )
        await conn.execute(
            """
            INSERT INTO piri_votes (board_id, choice_id, user_id)
            VALUES ($1, $2, $3)
            """,
            board_id, choice_id, user_id,
        )


@pytest.mark.asyncio
async def test_init_db_upgrades_old_schema_with_piri_boards():
    """Regression: DB เก่า (issues ไม่มีคอลัมน์ใหม่ + ไม่มีตาราง PIRI) → init_db ต้อง
    รัน migration 007 อัปเกรดให้ครบ ไม่ crash (บทเรียน: migrations ต้องรันก่อน index)"""
    parsed = urlparse(settings.DATABASE_URL)
    base_url = (
        f"{parsed.scheme}://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port}"
    )
    sys_url = f"{base_url}/postgres"
    db_name = f"piri_upgrade_test_{uuid.uuid4().hex}"

    # 1. สร้าง DB ทิ้ง (เฉพาะ test นี้ — ไม่แตะ session test DB)
    sys_conn = await asyncpg.connect(sys_url)
    try:
        await sys_conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await sys_conn.close()

    db_url = f"{base_url}/{db_name}"
    pool = await asyncpg.create_pool(db_url)
    try:
        # 2. จำลอง schema เก่า: issues ถูกสร้างไว้ก่อน (ไม่มี requested_destination /
        #    published_board_id — จุดที่ init_db ต้องอัปเกรดให้ผ่าน)
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE issues (
                    id SERIAL PRIMARY KEY,
                    room_id INTEGER,
                    main_category TEXT NOT NULL DEFAULT 'suggestion',
                    category TEXT NOT NULL DEFAULT 'academic',
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    image_url TEXT,
                    reporter_id INTEGER,
                    reporter_room_id INTEGER,
                    reporter_name TEXT,
                    current_level TEXT DEFAULT 'room',
                    current_assignee_id INTEGER,
                    current_assignee_role TEXT,
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'normal',
                    is_anonymous BOOLEAN DEFAULT FALSE,
                    resolved_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP DEFAULT NULL
                )
            """)

        # 3. รัน init_db (CREATE TABLEs → migrations → indexes) — ต้องไม่ crash
        await init_db(pool)

        # 4. 🔍 Deep verify: ถูกอัปเกรตครบ
        async with pool.acquire() as conn:
            for table in PIRI_TABLES:
                exists = await conn.fetchval(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = $1
                    """,
                    table,
                )
                assert exists, f"migration 007 ต้องสร้างตาราง {table} ให้ DB เก่า"

            has_dest = await conn.fetchval(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'issues' AND column_name = 'requested_destination'
                """
            )
            assert has_dest, "migration 007 ต้องเพิ่ม requested_destination ให้ DB เก่า"

            has_unique = await conn.fetchval(
                """
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'piri_votes' AND indexname = 'uq_piri_votes_board_user_active'
                """
            )
            assert has_unique, "unique index ของ piri_votes ต้องถูกสร้างหลัง migration"
    finally:
        await pool.close()

        # 5. cleanup: drop DB ที่สร้างใน test
        sys_conn = await asyncpg.connect(sys_url)
        try:
            await sys_conn.execute(
                f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{db_name}'
                AND pid <> pg_backend_pid();
                """
            )
            await sys_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        finally:
            await sys_conn.close()
