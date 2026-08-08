# === Issue Flow + Escalation Pyramid Tests ===
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


def _create_issue(client, users, *, topic="problem", category="discipline", title="เรื่องทดสอบ",
                  desc="รายละเอียด", anonymous=False, room_id=None):
    return client.post("/api/issues", json={
        "topic_type": topic, "category": category, "title": title,
        "description": desc, "is_anonymous": anonymous,
        "room_id": room_id or users["student"]["room_id"],
    }, headers={"Authorization": f"Bearer {users['student']['token']}"})


# === Section 1: Full flow (create → accept → step → escalate → resolve) ===
@pytest.mark.asyncio
async def test_full_issue_flow(client, issue_world):
    users = issue_world
    head, level, council = users["head"], users["level"], users["council"]

    # 1. สร้างเรื่อง (เริ่มระดับ room)
    res = _create_issue(client, users, title="เสียงดังรบกวน", desc="มีเสียงดังตอนพัก")
    assert res.status_code == 200
    issue_id = res.json()["id"]
    assert res.json()["current_level"] == "room"
    assert res.json()["status"] == "pending"

    # 2. หัวหน้าห้องรับ + countdown
    res = client.post(f"/api/issues/{issue_id}/accept", json={"estimated_days": 3},
                      headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 200
    res = client.get(f"/api/issues/{issue_id}", headers={"Authorization": f"Bearer {head['token']}"})
    assert res.json()["status"] == "in_progress"
    assert res.json()["countdown"]["estimated_days"] == 3

    # 3. เพิ่มขั้นตอน + ทำสำเร็จ
    res = client.post(f"/api/issues/{issue_id}/steps", json={"step_title": "ตรวจสอบ"},
                      headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 200
    step_id = res.json()["id"]
    res = client.patch(f"/api/issues/{issue_id}/steps/{step_id}/complete",
                       headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 200

    # 4. Escalate ไป level
    res = client.post(f"/api/issues/{issue_id}/escalate", json={"reason": "เกินความสามารถ"},
                      headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 200
    res = client.get(f"/api/issues/{issue_id}", headers={"Authorization": f"Bearer {level['token']}"})
    assert res.json()["current_level"] == "level"
    assert res.json()["status"] == "escalated"

    # 5. ประธานระดับรับ + resolve
    res = client.post(f"/api/issues/{issue_id}/accept", json={"estimated_days": 5},
                      headers={"Authorization": f"Bearer {level['token']}"})
    assert res.status_code == 200
    res = client.post(f"/api/issues/{issue_id}/resolve", json={"reason": "เรียบร้อย"},
                      headers={"Authorization": f"Bearer {level['token']}"})
    assert res.status_code == 200
    res = client.get(f"/api/issues/{issue_id}", headers={"Authorization": f"Bearer {council['token']}"})
    assert res.json()["status"] == "resolved"
    assert res.json()["resolved_at"] is not None


# === Section 2: Pyramid visibility ===
@pytest.mark.asyncio
async def test_pyramid_visibility(client, issue_world):
    users = issue_world
    student, council = users["student"], users["council"]

    # นักเรียนสร้างเรื่อง (anonymous)
    res = _create_issue(client, users, topic="problem", category="sanitation",
                        title="ห้องน้ำพัง", desc="ห้องน้ำชั้น 2 พัง", anonymous=True)
    assert res.status_code == 200
    issue_id = res.json()["id"]

    # นักเรียนเห็นเรื่องตัวเอง (แม้ anonymous — ติดตามสถานะ)
    res = client.get(f"/api/issues/{issue_id}", headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 200

    # Council เห็นทุกเรื่อง (พีระมิด)
    res = client.get("/api/issues", headers={"Authorization": f"Bearer {council['token']}"})
    assert res.status_code == 200
    assert any(i["id"] == issue_id for i in res.json())

    # นักเรียน (คนอื่น) ไม่เห็นเรื่องของคนอื่น
    res = client.get("/api/issues", headers={"Authorization": f"Bearer {student['token']}"})
    assert all(i["reporter_id"] == student["user_id"] for i in res.json())


# === Section 3: Permission checks ===
@pytest.mark.asyncio
async def test_cannot_accept_wrong_level(client, issue_world):
    """ประธานระดับ (level) ไม่สามารถรับเรื่องระดับ room ได้"""
    users = issue_world
    res = _create_issue(client, users, title="สนามบาสไฟไม่พอ", desc="ไฟสลัว")
    issue_id = res.json()["id"]

    # ประธานระดับพยายามรับเรื่องระดับ room → 403
    res = client.post(f"/api/issues/{issue_id}/accept", json={"estimated_days": 2},
                      headers={"Authorization": f"Bearer {users['level']['token']}"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_student_cannot_accept(client, issue_world):
    """นักเรียนธรรมดาไม่มีสิทธิ์รับเรื่อง"""
    users = issue_world
    res = _create_issue(client, users, title="เรื่องของคนอื่น", desc="aaa")
    issue_id = res.json()["id"]

    res = client.post(f"/api/issues/{issue_id}/accept", json={"estimated_days": 2},
                      headers={"Authorization": f"Bearer {users['student']['token']}"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_former_assignee_sees_escalated(client, issue_world):
    """หัวหน้าห้องที่เคยรับเรื่อง ยังเห็นเรื่องที่ escalate ขึ้นไป"""
    users = issue_world
    head, level = users["head"], users["level"]

    res = _create_issue(client, users, title="พัดลมดัง", desc="เบลทสั่น")
    issue_id = res.json()["id"]

    # หัวหน้าห้องรับแล้ว escalate
    client.post(f"/api/issues/{issue_id}/accept", json={"estimated_days": 3},
                headers={"Authorization": f"Bearer {head['token']}"})
    client.post(f"/api/issues/{issue_id}/escalate", json={"reason": "ต้องช่าง"},
                headers={"Authorization": f"Bearer {head['token']}"})

    # หัวหน้าห้อง (ระดับ room) ยังดูเรื่องที่ตอนนี้ level ได้ (อดีตผู้รับ)
    res = client.get(f"/api/issues/{issue_id}", headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 200
    assert res.json()["current_level"] == "level"
