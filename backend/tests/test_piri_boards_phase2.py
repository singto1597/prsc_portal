"""
PIRI Boards — Phase 2: Issue Service Adaptation
=================================================
ทดสอบ 2 ฟีเจอร์ใน issue_service:
1. create_issue รองรับ requested_destination ('normal'/'vote'/'talk')
   - vote/talk → start_level/current_level อัตโนมัติ = 'council' (bypass room/level)
     โดยไม่ต้องมีสิทธิ์ระดับสภา (ใครก็ "ขอ" เผยแพร่สาธารณะได้ — สภาเป็นคนอนุมัติ)
   - Audit log เก็บ requested_destination
2. approve_to_public — สภา/แอดมิน อนุมัติเรื่องขอสาธารณะเป็น PIRI Board
   - เฉพาะ council/admin ผ่าน (student 403)
   - ต้องเป็นเรื่องที่ขอปลายทางสาธารณะ (normal → 400)
   - board_type ต้องตรงกับที่ขอ (vote→talk → 400)
   - vote board ต้องมี choices ≥ 2
   - transaction เดียว: piri_boards + vote_choices + issues(published_board_id, status=resolved)
   - Audit action=APPROVE_TO_PUBLIC

Deep-DB verification ผ่าน db_pool (ไม่เชื่อ HTTP response อย่างเดียว)
"""
import json
import random
import uuid

import pytest
import pytest_asyncio

from services import auth_service


@pytest_asyncio.fixture
async def board_world(db_pool):
    """สร้าง room + users ครบชุด: student, council_member (สภาไม่ใช่แอดมิน), admin (แอดมินจริง)"""
    room_code = f"บ.{random.randint(1, 90)}"
    async with db_pool.acquire() as conn:
        room_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5') RETURNING id",
            room_code, room_code
        )

    users = {}
    for label, role in [
        ("student", "student"),
        ("council", "council_member"),  # สภานักเรียน (อำนาจสภา แต่ไม่ใช่ is_admin)
    ]:
        sid = f"B{random.randint(1000, 9999)}{label[:2].upper()}"
        uid = await auth_service.register_user(
            db_pool, sid, "1234", f"{label} ทดสอบ", sid, room_code, 1, role
        )
        users[label] = {
            "user_id": uid,
            "token": auth_service.create_access_token(uid),
            "room_id": room_id,
        }

    # admin: ประธานสภา + is_admin
    sid = f"B{random.randint(1000, 9999)}AD"
    uid = await auth_service.register_user(
        db_pool, sid, "1234", "แอดมิน ทดสอบ", sid, room_code, 1, "council_president"
    )
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE students SET is_admin = TRUE WHERE user_id = $1", uid)
    users["admin"] = {
        "user_id": uid,
        "token": auth_service.create_access_token(uid),
        "room_id": room_id,
    }

    # teacher: ครูทั่วไป — user_level() คืน 'council' (มองเห็นทั้งโรงเรียน) แต่ไม่ใช่อำนาจสภา
    sid = f"B{random.randint(1000, 9999)}TC"
    uid = await auth_service.register_user(
        db_pool, sid, "1234", "ครู ทดสอบ", sid, room_code, 1, "teacher"
    )
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE students SET staff_level = 'ม.5' WHERE user_id = $1", uid)
    users["teacher"] = {
        "user_id": uid,
        "token": auth_service.create_access_token(uid),
        "room_id": room_id,
    }
    return users


def _create_issue(client, world, *, destination="normal", title="เรื่องขอโพสต์สาธารณะ",
                  desc="รายละเอียด", token=None, anonymous=False):
    """ส่งคำขอเรื่อง (default student) — ระบุ requested_destination"""
    return client.post("/api/issues", json={
        "main_category": "report", "category": "complaint",
        "title": title, "description": desc,
        "is_anonymous": anonymous,
        "room_id": world["student"]["room_id"],
        "requested_destination": destination,
    }, headers={"Authorization": f"Bearer {token or world['student']['token']}"})


# ==================== 1) create_issue + requested_destination ====================
@pytest.mark.asyncio
async def test_create_issue_vote_sets_council_level_and_audit(client, board_world, db_pool):
    """vote → current_level='council' + requested_destination='vote' + audit ครบ (deep-DB)"""
    res = _create_issue(client, board_world, destination="vote")
    assert res.status_code == 200, res.text
    issue_id = res.json()["id"]
    assert res.json()["requested_destination"] == "vote"
    assert res.json()["current_level"] == "council"

    # 🔍 Deep-DB: ระดับจริงในตาราง + escalation room→council + audit
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT current_level, requested_destination FROM issues WHERE id = $1", issue_id
        )
        assert row["current_level"] == "council"
        assert row["requested_destination"] == "vote"

        esc = await conn.fetchrow(
            "SELECT from_level, to_level FROM issue_escalations WHERE issue_id = $1 ORDER BY id DESC LIMIT 1",
            issue_id
        )
        assert esc["from_level"] == "room" and esc["to_level"] == "council"

        audit = await conn.fetchrow(
            "SELECT new_values FROM audit_logs WHERE action = 'CREATE_ISSUE' AND entity_id = $1 ORDER BY id DESC LIMIT 1",
            str(issue_id)
        )
        assert audit, "ต้องมี audit CREATE_ISSUE"
        new_values = json.loads(audit["new_values"])
        assert new_values["requested_destination"] == "vote"
        assert new_values["current_level"] == "council"


@pytest.mark.asyncio
async def test_create_issue_talk_sets_council_level(client, board_world, db_pool):
    """talk → current_level='council' เช่นกัน"""
    res = _create_issue(client, board_world, destination="talk")
    assert res.status_code == 200, res.text
    issue_id = res.json()["id"]
    assert res.json()["requested_destination"] == "talk"
    assert res.json()["current_level"] == "council"

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT current_level, requested_destination FROM issues WHERE id = $1", issue_id
        )
        assert row["current_level"] == "council" and row["requested_destination"] == "talk"


@pytest.mark.asyncio
async def test_create_issue_normal_stays_room(client, board_world):
    """เรื่องปกติ (ไม่ระบุ destination) → requested_destination='normal' + ระดับ room (ไม่ regression)"""
    res = _create_issue(client, board_world, destination="normal")
    assert res.status_code == 200, res.text
    assert res.json()["requested_destination"] == "normal"
    assert res.json()["current_level"] == "room"


@pytest.mark.asyncio
async def test_create_issue_student_can_request_public_bypass_level_check(client, board_world, db_pool):
    """นักเรียนธรรมดาขอ vote/talk ได้ (bypass ระดับ) — ปกติ start_level=council ต้อง 403 แต่กรณีขอสาธารณะผ่าน"""
    # ตีเส้น: ถ้าไม่ bypass เรื่องระดับจะ 403 (student < council)
    res = _create_issue(client, board_world, destination="vote")
    assert res.status_code == 200, res.text
    assert res.json()["current_level"] == "council"

    async with db_pool.acquire() as conn:
        n = await conn.fetchval("SELECT count(*) FROM issues WHERE reporter_id = $1", board_world["student"]["user_id"])
    assert n == 1, "student สร้างเรื่องขอสาธารณะได้ 1 เรื่อง"


@pytest.mark.asyncio
async def test_create_issue_invalid_destination_422(client, board_world):
    """destination ผิดค่า → 422 (pydantic validator)"""
    res = _create_issue(client, board_world, destination="bogus")
    assert res.status_code == 422, res.text


# ==================== 2) approve_to_public ====================
@pytest.mark.asyncio
async def test_approve_to_public_vote_full_flow(client, board_world, db_pool):
    """สภา (council_member ไม่ใช่แอดมิน) อนุมัติ vote board → deep-DB ตรวจ piri_boards/choices/issues/audit"""
    issue_id = _create_issue(client, board_world, destination="vote").json()["id"]

    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "vote", "vote_choices": ["ตัวเลือก ก", "ตัวเลือก ข", "ตัวเลือก ค"]},
        headers={"Authorization": f"Bearer {board_world['council']['token']}"},
    )
    assert res.status_code == 200, res.text
    board_id = res.json()["board_id"]

    # 🔍 Deep-DB
    async with db_pool.acquire() as conn:
        board = await conn.fetchrow("SELECT * FROM piri_boards WHERE id = $1", board_id)
        assert board is not None
        assert board["board_type"] == "vote"
        assert board["title"] == "เรื่องขอโพสต์สาธารณะ"
        assert board["description"] == "รายละเอียด"
        assert board["source_issue_id"] == issue_id
        assert board["author_id"] == board_world["student"]["user_id"]  # ผู้แจ้งเดิมเป็นผู้เขียน
        assert board["approved_by"] == board_world["council"]["user_id"]
        assert board["approved_at"] is not None
        assert board["status"] == "active"

        choices = await conn.fetch(
            "SELECT choice_text, sort_order FROM piri_vote_choices WHERE board_id = $1 ORDER BY sort_order",
            board_id
        )
        assert [c["choice_text"] for c in choices] == ["ตัวเลือก ก", "ตัวเลือก ข", "ตัวเลือก ค"]
        assert [c["sort_order"] for c in choices] == [0, 1, 2]

        issue = await conn.fetchrow("SELECT * FROM issues WHERE id = $1", issue_id)
        assert issue["published_board_id"] == board_id
        assert issue["status"] == "resolved"
        assert issue["resolved_at"] is not None

        audit = await conn.fetchrow(
            "SELECT new_values, old_values FROM audit_logs WHERE action = 'APPROVE_TO_PUBLIC' ORDER BY id DESC LIMIT 1"
        )
        assert audit is not None
        nv = json.loads(audit["new_values"])
        assert nv["board_id"] == board_id
        assert nv["board_type"] == "vote"
        assert nv["published_board_id"] == board_id
        assert nv["status"] == "resolved"
        ov = json.loads(audit["old_values"])
        assert ov["requested_destination"] == "vote"

        history = await conn.fetchval(
            "SELECT status FROM issue_status_history WHERE issue_id = $1 ORDER BY id DESC LIMIT 1", issue_id
        )
        assert history == "resolved"

    # response ของ GET issue ต้องเห็น published_board_id
    res2 = client.get(f"/api/issues/{issue_id}",
                      headers={"Authorization": f"Bearer {board_world['student']['token']}"})
    assert res2.json()["published_board_id"] == board_id


@pytest.mark.asyncio
async def test_approve_to_public_talk_without_choices(client, board_world, db_pool):
    """talk board อนุมัติได้โดยไม่ต้องมีตัวเลือก"""
    issue_id = _create_issue(client, board_world, destination="talk").json()["id"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "talk"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text
    board_id = res.json()["board_id"]

    async with db_pool.acquire() as conn:
        board = await conn.fetchrow("SELECT board_type, source_issue_id, allow_comments FROM piri_boards WHERE id = $1", board_id)
        assert board["board_type"] == "talk"
        assert board["source_issue_id"] == issue_id
        assert board["allow_comments"] is True
        n_choices = await conn.fetchval("SELECT count(*) FROM piri_vote_choices WHERE board_id = $1", board_id)
        assert n_choices == 0


@pytest.mark.asyncio
async def test_approve_to_public_admin_can_approve(client, board_world, db_pool):
    """แอดมิน (is_admin) อนุมัติได้"""
    issue_id = _create_issue(client, board_world, destination="talk").json()["id"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "talk"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_approve_to_public_forbidden_for_student(client, board_world, db_pool):
    """นักเรียน (ไม่มีอำนาจสภา) อนุมัติ → 403 + ไม่มี board ถูกสร้าง"""
    issue_id = _create_issue(client, board_world, destination="vote").json()["id"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "vote", "vote_choices": ["ก", "ข"]},
        headers={"Authorization": f"Bearer {board_world['student']['token']}"},
    )
    assert res.status_code == 403, res.text

    async with db_pool.acquire() as conn:
        n_boards = await conn.fetchval("SELECT count(*) FROM piri_boards")
        assert n_boards == 0, "ต้องไม่มี board ถูกสร้างตอน 403"
        issue = await conn.fetchrow("SELECT status, published_board_id FROM issues WHERE id = $1", issue_id)
        assert issue["status"] != "resolved" and issue["published_board_id"] is None


@pytest.mark.asyncio
async def test_approve_to_public_forbidden_for_teacher(client, board_world, db_pool):
    """ครูทั่วไป (user_level คืน 'council' แต่ไม่ใช่ตำแหน่งสภา) → 403 (กัน privilege escalation)"""
    issue_id = _create_issue(client, board_world, destination="vote").json()["id"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "vote", "vote_choices": ["ก", "ข"]},
        headers={"Authorization": f"Bearer {board_world['teacher']['token']}"},
    )
    assert res.status_code == 403, res.text

    async with db_pool.acquire() as conn:
        n_boards = await conn.fetchval("SELECT count(*) FROM piri_boards")
        assert n_boards == 0, "ครูทั่วไปต้องสร้าง board ไม่ได้"


@pytest.mark.asyncio
async def test_approve_to_public_rejects_normal_issue(client, board_world, db_pool):
    """เรื่อง normal → 400 (ขอสาธารณะเท่านั้น)"""
    issue_id = _create_issue(client, board_world, destination="normal").json()["id"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "talk"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 400, res.text
    assert "ไม่ได้ขอเผยแพร่สาธารณะ" in res.text


@pytest.mark.asyncio
async def test_approve_to_public_rejects_wrong_board_type(client, board_world, db_pool):
    """ขอ vote แต่อนุมัติ talk → 400 (board_type ต้องตรงกับที่ขอ)"""
    issue_id = _create_issue(client, board_world, destination="vote").json()["id"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "talk"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_approve_to_public_vote_requires_choices(client, board_world):
    """vote board ไม่ส่งตัวเลือก/ส่ง 1 ตัว → 400 (pydantic) หรือ 400 (service)"""
    issue_id = _create_issue(client, board_world, destination="vote").json()["id"]
    # ไม่ส่ง vote_choices → pydantic อนุญาต (None) → service ต้อง reject 400
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "vote"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 400, res.text
    assert "ตัวเลือก" in res.text


@pytest.mark.asyncio
async def test_approve_to_public_twice_conflict(client, board_world, db_pool):
    """อนุมัติซ้ำ → 409 + ยังเป็น board เดิม"""
    issue_id = _create_issue(client, board_world, destination="vote").json()["id"]
    first = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "vote", "vote_choices": ["ก", "ข"]},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert first.status_code == 200
    board_id = first.json()["board_id"]

    second = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "vote", "vote_choices": ["ค", "ง"]},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert second.status_code == 409, second.text

    async with db_pool.acquire() as conn:
        n_boards = await conn.fetchval("SELECT count(*) FROM piri_boards WHERE source_issue_id = $1", issue_id)
        assert n_boards == 1, "ต้องมี board เดียวเท่านั้น (ไม่สร้างซ้ำ)"


@pytest.mark.asyncio
async def test_approve_to_public_missing_issue_404(client, board_world):
    """issue ไม่มี → 404"""
    res = client.post(
        f"/api/issues/{random.randint(90000, 99999)}/approve-to-public",
        json={"board_type": "talk"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 404, res.text
