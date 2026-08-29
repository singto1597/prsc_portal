"""
PIRI Boards — เปลี่ยนปลายทาง (requested_destination) ของเรื่อง
=============================================================
แก้กรณีแจ้งผิด เช่น ควรเป็น "บอร์ดพูดคุย" แต่แจ้งมาเป็น "ดำเนินการปกติ":
- หัวหน้าห้อง/รอง (RECEIVE_ISSUES ในห้องเรื่อง) เปลี่ยนเรื่องระดับห้อง → 'talk'/'vote' → ส่งสภานักเรียน
- สภานักเรียน/แอดมิน เปลี่ยนได้ทุกเรื่อง (ทั้งสองทาง)
- เปลี่ยนปลายทางสาธารณะ (vote/talk) → current_level='council' + pending (เคลียร์ assignee/countdown)
- เปลี่ยนกลับ 'normal' → current_level='room' + pending
- ระดับไม่เปลี่ยน (talk→vote ยังอยู่สภา) → เปลี่ยนแค่ปลายทาง ไม่รีเซ็ตสถานะ
- กัน: เรื่องที่เผยแพร่เป็น board แล้ว (409) / เรื่องที่ปิดแล้ว (409) / ผู้ไม่มีสิทธิ์ (403) / ค่าไม่ถูก (422)

Deep-DB verification ผ่าน db_pool (ตาม docs/rules/testing.md)
"""
import json
import random

import pytest
import pytest_asyncio

from services import auth_service


@pytest_asyncio.fixture
async def dest_world(db_pool):
    """room หลัก (เรื่องเกิดที่นี่) + student + head (หัวหน้าห้องห้องเดียวกัน)
    + other_head (หัวหน้าห้องห้องอื่น) + council (สภา) + admin"""
    room_code = f"บ.{random.randint(1, 90)}"
    other_room_code = f"บ.{random.randint(91, 99)}"
    async with db_pool.acquire() as conn:
        room_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5') RETURNING id",
            room_code, room_code
        )
        other_room_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5') RETURNING id",
            other_room_code, other_room_code
        )

    users = {}
    for label, role, rcode, no in [
        ("student", "student", room_code, 1),
        ("head", "class_president", room_code, 2),
        ("other_head", "class_president", other_room_code, 3),
        ("council", "council_member", room_code, 4),
    ]:
        sid = f"P{random.randint(1000, 9999)}{label[:2].upper()}"
        uid = await auth_service.register_user(
            db_pool, sid, "1234", f"{label} ทดสอบ", sid, rcode, no, role
        )
        users[label] = {
            "user_id": uid,
            "token": auth_service.create_access_token(uid),
            "room_id": room_id if rcode == room_code else other_room_id,
        }

    # admin (is_admin)
    sid = f"P{random.randint(1000, 9999)}AD"
    uid = await auth_service.register_user(
        db_pool, sid, "1234", "แอดมิน ทดสอบ", sid, room_code, 5, "council_president"
    )
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE students SET is_admin = TRUE WHERE user_id = $1", uid)
    users["admin"] = {
        "user_id": uid,
        "token": auth_service.create_access_token(uid),
        "room_id": room_id,
    }
    return users


def _create_issue(client, world, *, destination="normal", actor="student"):
    """สร้างเรื่อง (default: normal ระดับห้อง) — คืน issue_id"""
    res = client.post("/api/issues", json={
        "main_category": "report", "category": "complaint",
        "title": "เรื่องเปลี่ยนปลายทาง", "description": "รายละเอียด",
        "is_anonymous": False,
        "room_id": world["student"]["room_id"],
        "requested_destination": destination,
    }, headers={"Authorization": f"Bearer {world[actor]['token']}"})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _change(client, world, issue_id, destination, actor):
    return client.patch(
        f"/api/issues/{issue_id}/destination",
        json={"requested_destination": destination},
        headers={"Authorization": f"Bearer {world[actor]['token']}"},
    )


@pytest.mark.asyncio
async def test_room_head_changes_normal_to_talk_routes_to_council(client, dest_world, db_pool):
    """หัวหน้าห้องเปลี่ยน 'normal' → 'talk' → ระดับสภา + pending + audit (deep-DB)"""
    issue_id = _create_issue(client, dest_world, destination="normal")

    res = _change(client, dest_world, issue_id, "talk", actor="head")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["requested_destination"] == "talk"
    assert data["current_level"] == "council"
    assert data["status"] == "pending"
    assert data["current_assignee_id"] is None

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT requested_destination, current_level, status, current_assignee_id FROM issues WHERE id = $1",
            issue_id
        )
        assert row["requested_destination"] == "talk"
        assert row["current_level"] == "council"
        assert row["status"] == "pending"
        assert row["current_assignee_id"] is None
        audit = await conn.fetchrow(
            "SELECT old_values, new_values FROM audit_logs WHERE action = 'CHANGE_DESTINATION' ORDER BY created_at DESC LIMIT 1"
        )
        assert audit, "ต้องมี audit CHANGE_DESTINATION"
        assert json.loads(audit["old_values"])["requested_destination"] == "normal"
        assert json.loads(audit["new_values"])["requested_destination"] == "talk"
        hist = await conn.fetchrow(
            "SELECT status, note FROM issue_status_history WHERE issue_id = $1 ORDER BY created_at DESC LIMIT 1",
            issue_id
        )
        assert hist["status"] == "pending"
        assert "talk" in hist["note"]


@pytest.mark.asyncio
async def test_head_of_other_room_forbidden(client, dest_world):
    """หัวหน้าห้องห้องอื่น → 403 (ไม่ใช่ผู้รับเรื่องในห้องนี้)"""
    issue_id = _create_issue(client, dest_world, destination="normal")
    res = _change(client, dest_world, issue_id, "talk", actor="other_head")
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_plain_student_forbidden(client, dest_world):
    """นักเรียนธรรมดา (ไม่ใช่หัวหน้าห้อง/สภา) → 403"""
    issue_id = _create_issue(client, dest_world, destination="normal")
    res = _change(client, dest_world, issue_id, "talk", actor="student")
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_council_changes_talk_to_normal_routes_to_room(client, dest_world, db_pool):
    """สภาเปลี่ยน 'talk' → 'normal' → กลับไประดับห้อง (pending)"""
    issue_id = _create_issue(client, dest_world, destination="talk")
    res = _change(client, dest_world, issue_id, "normal", actor="council")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["requested_destination"] == "normal"
    assert data["current_level"] == "room"

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT requested_destination, current_level, status FROM issues WHERE id = $1", issue_id
        )
        assert row["requested_destination"] == "normal"
        assert row["current_level"] == "room"
        assert row["status"] == "pending"


@pytest.mark.asyncio
async def test_change_within_same_level_keeps_status(client, dest_world, db_pool):
    """talk→vote (ยังอยู่สภา ระดับไม่เปลี่ยน) → เปลี่ยนแค่ปลายทาง ไม่รีเซ็ตสถานะ/ผู้รับ"""
    issue_id = _create_issue(client, dest_world, destination="talk")
    # สภารับเรื่องก่อน (in_progress + assignee)
    accept = client.post(
        f"/api/issues/{issue_id}/accept", json={"estimated_days": 5},
        headers={"Authorization": f"Bearer {dest_world['council']['token']}"},
    )
    assert accept.status_code == 200, accept.text

    res = _change(client, dest_world, issue_id, "vote", actor="council")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["requested_destination"] == "vote"
    assert data["current_level"] == "council"
    assert data["status"] == "in_progress", "ระดับไม่เปลี่ยน → ต้องไม่รีเซ็ตสถานะ"
    assert data["current_assignee_id"] == dest_world["council"]["user_id"]


@pytest.mark.asyncio
async def test_countdown_cleared_when_level_changes(client, dest_world, db_pool):
    """หัวหน้าห้องรับเรื่อง (ตั้ง countdown) → เปลี่ยนเป็น talk → countdown ถูก soft-delete"""
    issue_id = _create_issue(client, dest_world, destination="normal")
    accept = client.post(
        f"/api/issues/{issue_id}/accept", json={"estimated_days": 7},
        headers={"Authorization": f"Bearer {dest_world['head']['token']}"},
    )
    assert accept.status_code == 200, accept.text

    async with db_pool.acquire() as conn:
        has_countdown = await conn.fetchval(
            "SELECT COUNT(*) FROM issue_countdowns WHERE issue_id = $1", issue_id
        )
        assert has_countdown == 1, "ต้องมี countdown หลังรับเรื่อง"

    res = _change(client, dest_world, issue_id, "talk", actor="head")
    assert res.status_code == 200, res.text

    async with db_pool.acquire() as conn:
        active_countdown = await conn.fetchval(
            "SELECT COUNT(*) FROM issue_countdowns WHERE issue_id = $1", issue_id
        )
        assert active_countdown == 0, "เปลี่ยนไประดับใหม่ต้องเคลียร์ countdown"


@pytest.mark.asyncio
async def test_published_issue_cannot_change_409(client, dest_world):
    """เรื่องที่เผยแพร่เป็น board แล้ว → 409"""
    issue_id = _create_issue(client, dest_world, destination="talk")
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "talk", "allow_comments": True},
        headers={"Authorization": f"Bearer {dest_world['council']['token']}"},
    )
    assert res.status_code == 200, res.text

    res = _change(client, dest_world, issue_id, "normal", actor="council")
    assert res.status_code == 409, res.text


@pytest.mark.asyncio
async def test_closed_issue_cannot_change_409(client, dest_world):
    """เรื่องที่ปิดแล้ว (resolved) → 409"""
    issue_id = _create_issue(client, dest_world, destination="normal")
    # หัวหน้าห้องรับ + ปิดเรื่อง
    client.post(
        f"/api/issues/{issue_id}/accept", json={"estimated_days": 3},
        headers={"Authorization": f"Bearer {dest_world['head']['token']}"},
    )
    res = client.post(
        f"/api/issues/{issue_id}/resolve", json={"reason": "แก้เสร็จ"},
        headers={"Authorization": f"Bearer {dest_world['head']['token']}"},
    )
    assert res.status_code == 200, res.text

    res = _change(client, dest_world, issue_id, "talk", actor="council")
    assert res.status_code == 409, res.text


@pytest.mark.asyncio
async def test_invalid_destination_422(client, dest_world):
    issue_id = _create_issue(client, dest_world, destination="normal")
    res = client.patch(
        f"/api/issues/{issue_id}/destination", json={"requested_destination": "podcast"},
        headers={"Authorization": f"Bearer {dest_world['head']['token']}"},
    )
    assert res.status_code == 422, res.text
