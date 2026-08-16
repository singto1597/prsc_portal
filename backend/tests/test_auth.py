# === Auth Flow Tests ===
import pytest
import pytest_asyncio
import asyncpg

from services import auth_service


@pytest_asyncio.fixture
async def room(db_pool):
    """สร้าง room มาตรฐานสำหรับ test"""
    async with db_pool.acquire() as conn:
        room = await conn.fetchval(
            "SELECT id FROM rooms WHERE room_code = 'ม.4/1' AND deleted_at IS NULL"
        )
        if not room:
            room = await conn.fetchval(
                "INSERT INTO rooms (room_code, room_name, level) VALUES ('ม.4/1','ม.4/1','ม.4') RETURNING id"
            )
        return room


@pytest_asyncio.fixture
async def created_user(db_pool, room):
    """สร้าง user student + return (username, password, user_id)"""
    import random
    username = f"stu_{random.randint(1000, 9999)}"
    password = "1234"
    uid = await auth_service.register_user(
        db_pool, username, password, "ทดสอบ ระบบ",
        f"ID{username}", "ม.4/1", 1, "student"
    )
    return username, password, uid


# === Section 1: Login happy path ===
@pytest.mark.asyncio
async def test_login_success(client, created_user):
    """Login ด้วย username/password ถูกต้อง ได้ JWT + roles"""
    username, password, _ = created_user
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    data = res.json()
    assert data["access_token"]
    assert data["user"]["username"] == username
    assert data["user"]["roles"]  # มี roles อย่างน้อย 1


# === Section 2: Failures ===
@pytest.mark.asyncio
async def test_login_wrong_password(client, created_user):
    """Login ด้วยรหัสผิด → 401"""
    username, _, _ = created_user
    res = client.post("/api/auth/login", json={"username": username, "password": "wrongpass"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_missing_user(client):
    """Login ด้วย user ที่ไม่มี → 401"""
    res = client.post("/api/auth/login", json={"username": "not_exists_xyz", "password": "1234"})
    assert res.status_code == 401


# === Section 3: /me ===
@pytest.mark.asyncio
async def test_me_requires_auth(client):
    """GET /auth/me ไม่มี token → 401"""
    res = client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client, created_user):
    """GET /auth/me มี token → 200 + ข้อมูล user"""
    username, password, _ = created_user
    login = client.post("/api/auth/login", json={"username": username, "password": password})
    token = login.json()["access_token"]

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["username"] == username


# === Section 4: School-wide role (admin/ครูสภา — ไม่ผูกห้อง) ===
@pytest.mark.asyncio
async def test_admin_school_wide_profile_and_me(client, db_pool):
    """admin/ครูสภา (room_id NULL) login → /me + /students/me/profile ได้ ไม่ 404"""
    import random
    username = f"adm{random.randint(100000, 999999)}"  # ≤10 chars (student_id เป็น VARCHAR(10))
    uid = await auth_service.register_user(
        db_pool, username, "1234", "แอดมิน ระบบ",
        username, "", 0, "admin"
    )

    login = client.post("/api/auth/login", json={"username": username, "password": "1234"})
    assert login.status_code == 200
    data = login.json()
    assert data["user"]["roles"], "admin ต้องมี roles (แม้ไม่มีห้อง)"
    # role admin ต้องมี is_admin + permissions ครบ (จาก roles.json)
    assert data["user"]["roles"][0]["role"] == "admin"
    assert data["user"]["roles"][0]["is_admin"] is True

    token = data["access_token"]
    # /auth/me
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["roles"][0]["role"] == "admin"
    # /students/me/profile (LEFT JOIN rooms — ไม่ 404 เพราะไม่มีห้อง)
    res = client.get("/api/students/me/profile", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["class_role"] == "admin"
    assert res.json()["room_id"] is None
