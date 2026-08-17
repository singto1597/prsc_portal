"""
Regression: init_db ต้องรัน migrations ก่อนสร้าง index

เรื่องจริงบน staging: หลัง deploy schema ใหม่ (หมวดหมู่รื้อใหม่ — migration 001 เพิ่ม
`issues.main_category`) backend crash-loop ทุก replica ด้วย
`UndefinedColumnError: column "main_category" does not exist`
เพราะ init_db สร้าง `idx_issues_main_category ON issues(main_category)` ก่อนที่
migration จะเพิ่มคอลัมน์ให้ DB เดิม

Test นี้จำลอง DB "เก่า" (issues ที่ไม่มี main_category) แล้วรัน init_db ซ้ำ
ต้องสำเร็จ + main_category + index ถูกสร้าง — กัน regression ที่กลับไปสร้าง index ก่อน migration
"""
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest

from core.config import settings
from core.init_db import init_db


@pytest.mark.asyncio
async def test_init_db_upgrades_old_schema_without_main_category():
    """DB เก่าที่ issues ยังไม่มี main_category → init_db ต้องไม่ crash และอัปเกรดให้ครบ"""
    parsed = urlparse(settings.DATABASE_URL)
    base_url = (
        f"{parsed.scheme}://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port}"
    )
    sys_url = f"{base_url}/postgres"
    db_name = f"upgrade_test_{uuid.uuid4().hex}"

    # 1. สร้าง DB ทิ้ง (เฉพาะสำหรับ test นี้ — ไม่แตะ session test DB)
    sys_conn = await asyncpg.connect(sys_url)
    try:
        await sys_conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await sys_conn.close()

    db_url = f"{base_url}/{db_name}"
    pool = await asyncpg.create_pool(db_url)
    try:
        # 2. จำลอง schema เก่า: issues ถูกสร้างไว้ก่อน (ไม่มี main_category, ไม่มี FK เพื่อ
        #    ให้สร้างได้โดยไม่ต้องมี rooms มาก่อน — จุดที่ init_db ต้องอัปเกรดให้ผ่าน)
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE issues (
                    id SERIAL PRIMARY KEY,
                    room_id INTEGER,
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

        # 4. 🔍 Deep verify: main_category ถูกเพิ่ม + index ถูกสร้าง
        async with pool.acquire() as conn:
            has_main = await conn.fetchval(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'issues' AND column_name = 'main_category'
                """
            )
            assert has_main, "migration 001 ต้องเพิ่มคอลัมน์ main_category ให้ DB เก่า"

            has_index = await conn.fetchval(
                """
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'issues' AND indexname = 'idx_issues_main_category'
                """
            )
            assert has_index, "index idx_issues_main_category ต้องถูกสร้างหลัง migration"
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
