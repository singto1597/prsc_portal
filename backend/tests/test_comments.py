# === Issue Comments Tests (คอมเมนต์แบบ YouTube) ===
import random
import pytest
import pytest_asyncio

from services import auth_service


@pytest_asyncio.fixture
async def issue_world(db_pool):
    """สร้าง room + users ครบชุด: นักเรียน, หัวหน้าห้อง, ประธานระดับ, ประธานสภา"""
    room_code = f"ม.4/{random.randint(1, 90)}"
    async with db_pool.acquire() as conn:
        room_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.4') RETURNING id",
            room_code, room_code
        )

    users = {}
    for label, role in [
        ("student", "student"),
        ("head", "class_president"),
        ("level", "level_president"),
        ("council", "council_president"),
    ]:
        sid = f"T{random.randint(1000, 9999)}{role[:2]}"
        uid = await auth_service.register_user(
            db_pool, sid, "1234", f"{label} ทดสอบ", sid, room_code, 1, role
        )
        if role == "council_president":
            async with db_pool.acquire() as conn:
                await conn.execute("UPDATE students SET is_admin = TRUE WHERE user_id = $1", uid)
        users[label] = {
            "user_id": uid,
            "token": auth_service.create_access_token(uid),
            "room_id": room_id,
        }
    return users


def _create_issue(client, users, *, main_category="report", category="complaint", title="เรื่องทดสอบ",
                  desc="รายละเอียด", anonymous=False, room_id=None, token=None):
    return client.post("/api/issues", json={
        "main_category": main_category, "category": category, "title": title,
        "description": desc, "is_anonymous": anonymous,
        "room_id": room_id or users["student"]["room_id"],
    }, headers={"Authorization": f"Bearer {token or users['student']['token']}"})


# === create ===
@pytest.mark.asyncio
async def test_create_comment(client, issue_world, db_pool):
    users = issue_world
    student = users["student"]

    res = _create_issue(client, users, title="เรื่องคอมเมนต์", desc="aaa")
    issue_id = res.json()["id"]

    res = client.post(f"/api/issues/{issue_id}/comments", json={"body": "รับทราบครับ"},
                      headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 200, res.text
    assert res.json()["body"] == "รับทราบครับ"
    assert res.json()["commenter_name"] == "student ทดสอบ"
    assert res.json()["user_id"] == student["user_id"]

    # deep-DB verify
    async with db_pool.acquire() as conn:
        c = await conn.fetchrow("SELECT * FROM issue_comments WHERE issue_id = $1", issue_id)
        assert c["user_id"] == student["user_id"]
        assert c["commenter_name"] == "student ทดสอบ"
        assert c["body"] == "รับทราบครับ"
        assert c["deleted_at"] is None
        assert c["updated_at"] is None
        audit = await conn.fetchval(
            "SELECT 1 FROM audit_logs WHERE action = 'CREATE_COMMENT' AND entity_id = $1",
            str(c["id"]))
        assert audit == 1


@pytest.mark.asyncio
async def test_comment_on_anonymous_issue_shows_name(client, issue_world):
    users = issue_world
    student, head = users["student"], users["head"]

    res = _create_issue(client, users, title="นิรนาม", desc="aaa", anonymous=True)
    issue_id = res.json()["id"]

    # เรื่อง anonymous แต่คอมเมนต์แสดงชื่อจริงของผู้คอมเมนต์เสมอ
    res = client.post(f"/api/issues/{issue_id}/comments", json={"body": "ตรวจแล้วครับ"},
                      headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 200
    assert res.json()["commenter_name"] == "head ทดสอบ"


@pytest.mark.asyncio
async def test_comment_empty_body_422(client, issue_world):
    users = issue_world
    res = _create_issue(client, users, title="เรื่อง", desc="aaa")
    issue_id = res.json()["id"]

    res = client.post(f"/api/issues/{issue_id}/comments", json={"body": ""},
                      headers={"Authorization": f"Bearer {users['student']['token']}"})
    assert res.status_code == 422


# === edit own ===
@pytest.mark.asyncio
async def test_edit_own_comment(client, issue_world, db_pool):
    users = issue_world
    student = users["student"]

    res = _create_issue(client, users, title="เรื่อง", desc="aaa")
    issue_id = res.json()["id"]
    res = client.post(f"/api/issues/{issue_id}/comments", json={"body": "เดิม"},
                      headers={"Authorization": f"Bearer {student['token']}"})
    comment_id = res.json()["id"]

    res = client.patch(f"/api/issues/{issue_id}/comments/{comment_id}", json={"body": "แก้แล้ว"},
                       headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 200, res.text
    assert res.json()["body"] == "แก้แล้ว"
    assert res.json()["updated_at"] is not None

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT body, updated_at FROM issue_comments WHERE id = $1", comment_id)
        assert row["body"] == "แก้แล้ว"
        assert row["updated_at"] is not None


# === delete own (soft) ===
@pytest.mark.asyncio
async def test_delete_comment_soft(client, issue_world, db_pool):
    users = issue_world
    student = users["student"]

    res = _create_issue(client, users, title="เรื่อง", desc="aaa")
    issue_id = res.json()["id"]
    res = client.post(f"/api/issues/{issue_id}/comments", json={"body": "จะลบ"},
                      headers={"Authorization": f"Bearer {student['token']}"})
    comment_id = res.json()["id"]

    res = client.delete(f"/api/issues/{issue_id}/comments/{comment_id}",
                        headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 200

    # deep-DB: soft delete — row ยังอยู่ deleted_at NOT NULL
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT deleted_at FROM issue_comments WHERE id = $1", comment_id)
        assert row["deleted_at"] is not None


# === cannot edit/delete others' ===
@pytest.mark.asyncio
async def test_cannot_edit_or_delete_others_comment(client, issue_world, db_pool):
    users = issue_world
    student, head = users["student"], users["head"]

    res = _create_issue(client, users, title="เรื่อง", desc="aaa")
    issue_id = res.json()["id"]
    res = client.post(f"/api/issues/{issue_id}/comments", json={"body": "ของ student"},
                      headers={"Authorization": f"Bearer {student['token']}"})
    comment_id = res.json()["id"]

    # หัวหน้าห้องไม่ใช่ผู้เขียน → แก้/ลบไม่ได้ (403)
    res = client.patch(f"/api/issues/{issue_id}/comments/{comment_id}", json={"body": "แฮก"},
                       headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 403
    res = client.delete(f"/api/issues/{issue_id}/comments/{comment_id}",
                        headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 403

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT body, deleted_at FROM issue_comments WHERE id = $1", comment_id)
        assert row["body"] == "ของ student"
        assert row["deleted_at"] is None


# === invisible issue → 403 ===
@pytest.mark.asyncio
async def test_comment_on_invisible_issue_403(client, db_pool):
    room_a = f"ม.4/{random.randint(100, 200)}"
    room_b = f"ม.5/{random.randint(100, 200)}"
    async with db_pool.acquire() as conn:
        room_a_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.4') RETURNING id",
            room_a, room_a
        )
        room_b_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5') RETURNING id",
            room_b, room_b
        )

    sid_a = f"A{random.randint(1000, 9999)}"
    sid_b = f"B{random.randint(1000, 9999)}"
    uid_a = await auth_service.register_user(db_pool, sid_a, "1234", "คนห้อง A", sid_a, room_a, 1, "student")
    uid_b = await auth_service.register_user(db_pool, sid_b, "1234", "คนห้อง B", sid_b, room_b, 1, "student")
    users = {
        "a": {"user_id": uid_a, "token": auth_service.create_access_token(uid_a), "room_id": room_a_id},
        "b": {"user_id": uid_b, "token": auth_service.create_access_token(uid_b), "room_id": room_b_id},
    }

    # เรื่องในห้อง A (สร้างโดยคนห้อง A)
    res = _create_issue(client, users, title="เรื่องห้อง A", room_id=room_a_id, token=users["a"]["token"])
    assert res.status_code == 200
    issue_id = res.json()["id"]

    # คนห้อง B มองไม่เห็น → คอมเมนต์ไม่ได้ (403)
    res = client.post(f"/api/issues/{issue_id}/comments", json={"body": "ขอกวน"},
                      headers={"Authorization": f"Bearer {users['b']['token']}"})
    assert res.status_code == 403


# === embedded in detail, oldest-first, deleted hidden ===
@pytest.mark.asyncio
async def test_comments_embedded_in_detail(client, issue_world):
    users = issue_world
    student, head = users["student"], users["head"]

    res = _create_issue(client, users, title="เรื่อง", desc="aaa")
    issue_id = res.json()["id"]

    # head คอมเมนต์แรก, student คอมเมนต์ที่สอง
    r1 = client.post(f"/api/issues/{issue_id}/comments", json={"body": "แรก"},
                     headers={"Authorization": f"Bearer {head['token']}"})
    r2 = client.post(f"/api/issues/{issue_id}/comments", json={"body": "ที่สอง"},
                     headers={"Authorization": f"Bearer {student['token']}"})
    c1, c2 = r1.json()["id"], r2.json()["id"]
    assert c1 != c2

    # ลบคอมเมนต์แรก (ของ head เอง) → detail เหลือแค่ c2
    res = client.delete(f"/api/issues/{issue_id}/comments/{c1}",
                        headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 200

    res = client.get(f"/api/issues/{issue_id}", headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 200
    comments = res.json()["comments"]
    assert len(comments) == 1
    assert comments[0]["id"] == c2
    assert comments[0]["user_id"] == student["user_id"]
    assert comments[0]["body"] == "ที่สอง"


@pytest.mark.asyncio
async def test_comments_oldest_first(client, issue_world):
    users = issue_world
    student = users["student"]

    res = _create_issue(client, users, title="เรื่อง", desc="aaa")
    issue_id = res.json()["id"]

    for body in ["หนึ่ง", "สอง", "สาม"]:
        res = client.post(f"/api/issues/{issue_id}/comments", json={"body": body},
                          headers={"Authorization": f"Bearer {student['token']}"})
        assert res.status_code == 200

    res = client.get(f"/api/issues/{issue_id}", headers={"Authorization": f"Bearer {student['token']}"})
    comments = res.json()["comments"]
    assert [c["body"] for c in comments] == ["หนึ่ง", "สอง", "สาม"]
