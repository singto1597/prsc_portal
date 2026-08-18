# === Seed Users Tests (บัญชี admin/ครูสภา/ประธานสภา อัตโนมัติ) ===
"""
⚠️ ไม่ใช้ fixture `client` ในไฟล์นี้ เพราะ lifespan ของ TestClient จะ seed users เอง
ก่อนที่เราจะ seed เอง (ทำให้ seed รอบเราถูก skip = {}).
วิธีที่ถูก: seed เองก่อน → ค่อยสร้าง TestClient ภายใน test (ล็อกได้ว่า seed ด้วย creds ที่รู้จัก)
"""
import os
from contextlib import contextmanager
from fastapi.testclient import TestClient

import pytest

from core.seed_users import seed_default_users
from core.config import settings
from main import app


@contextmanager
def _client_for(test_db_url):
    """TestClient ที่ชี้ไป test DB (เลียนแบบ fixture client แต่ควบคุม seed ได้เอง)"""
    original_db_url = settings.DATABASE_URL
    settings.DATABASE_URL = test_db_url
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        settings.DATABASE_URL = original_db_url


@pytest.mark.asyncio
async def test_seed_users_created_and_login(db_pool, test_db_url):
    """seed สร้างครบ 3 role, login ได้, ตั้ง must_change_password=True"""
    creds = await seed_default_users(db_pool)
    assert set(creds.keys()) == {"admin", "teacher_council", "council_president"}

    with _client_for(test_db_url) as client:
        for role, info in creds.items():
            login = client.post("/api/auth/login", json={
                "username": info["username"], "password": info["password"],
            })
            assert login.status_code == 200, f"login {role} ล้มเหลว: {login.text}"
            data = login.json()
            assert data["user"]["must_change_password"] is True, f"{role} ต้องตั้ง flag"
            assert data["user"]["roles"][0]["role"] == role
            # ตรวจใน DB ว่า user ฝาก flag ที่ users + is_admin ที่ students
            async with db_pool.acquire() as conn:
                user_id = data["user"]["id"]
                assert await conn.fetchval(
                    "SELECT must_change_password FROM users WHERE id=$1", user_id
                ) is True
                assert await conn.fetchval(
                    "SELECT is_admin FROM students WHERE user_id=$1", user_id
                ) is True


@pytest.mark.asyncio
async def test_seed_users_idempotent(db_pool):
    """เรียก seed ซ้ำ → ไม่สร้างบัญชีซ้ำ (จำนวน admin เดิมเท่าเดิม)"""
    first = await seed_default_users(db_pool)
    assert first, "ต้อง seed รอบแรกได้"

    async def count_privileged():
        async with db_pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT count(*) FROM students
                WHERE class_role IN ('admin','teacher_council','council_president')
                  AND deleted_at IS NULL
                """
            )

    before = await count_privileged()
    second = await seed_default_users(db_pool)
    assert second == {}, "seed รอบสองต้องข้าม (มีผู้ใช้แล้ว)"
    assert await count_privileged() == before, "ต้องไม่มีบัญชีซ้ำ"


@pytest.mark.asyncio
async def test_change_password_clears_flag(db_pool, test_db_url):
    """เปลี่ยนรหัสผ่านสำเร็จ → must_change_password กลับเป็น False"""
    creds = await seed_default_users(db_pool)
    info = creds["admin"]

    with _client_for(test_db_url) as client:
        login = client.post("/api/auth/login", json={
            "username": info["username"], "password": info["password"],
        })
        token = login.json()["access_token"]
        assert login.json()["user"]["must_change_password"] is True

        # เปลี่ยนรหัส (ใช้รหัสชั่วคราวเป็น old)
        new_password = "New_Pass_9876"
        res = client.post("/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"old_password": info["password"], "new_password": new_password})
        assert res.status_code == 200

        # /me → flag false แล้ว
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["must_change_password"] is False

        # login ด้วยรหัสใหม่ได้ + flag false
        login2 = client.post("/api/auth/login", json={
            "username": info["username"], "password": new_password,
        })
        assert login2.status_code == 200
        assert login2.json()["user"]["must_change_password"] is False


@pytest.mark.asyncio
async def test_seed_credentials_file_written(db_pool):
    """seed เขียนไฟล์ credentials ลง disk"""
    await seed_default_users(db_pool)
    path = os.path.abspath(settings.SEED_CREDENTIALS_FILE)
    assert os.path.isfile(path), "ต้องมีไฟล์ credentials"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # ไฟล์ต้องมี keyword บอกชัดว่าต้องเปลี่ยนรหัส
    assert "Username" in content and "Password" in content
    assert "เปลี่ยนรหัส" in content
