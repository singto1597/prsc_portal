"""
PIRI Boards — Phase 5: Moderation + Report (PIRI Talk)
=======================================================
ทดสอบ:
1. report_comment   — นักเรียนแจ้งความไม่เหมาะสม (เหตุผล/แจ้งซ้ำ 409/แจ้งตัวเอง 400/ไม่พบ 404/auth)
2. hide_comment     — สภา/แอดมินซ่อน (subtree + ลด comment_count + หายจาก detail + ปิดรายงาน)
3. unhide_comment   — กลับมาแสดง (เพิ่ม comment_count คืน)
4. hide/unhide_board — ซ่อน board ทั้งบอร์ด (feed/detail 404)
5. resolve_report   — จัดการรายงาน: hide (ซ่อน+ลด counter) / dismiss (ปัดตก ไม่ซ่อน)
6. list_reports     — คิวรายงาน (เฉพาะสภา/แอดมิน + กรอง/ค้นหา)
7. 🔧 Counter integrity — comment_count ตรงกับคอมเมนต์ที่ยังแสดงจริงเสมอ (หัวใจของ Phase 5)

Deep-DB verification ผ่าน db_pool (ไม่เชื่อ HTTP response อย่างเดียว — ตาม docs/rules/testing.md)
"""
import json
import random

import pytest
import pytest_asyncio

from services import auth_service


@pytest_asyncio.fixture
async def board_world(db_pool):
    """สร้าง room + users ครบชุด: student (ผู้โหวต/คอมเมนต์/แจ้ง), council, admin (จัดการได้)"""
    room_code = f"บ.{random.randint(1, 90)}"
    async with db_pool.acquire() as conn:
        room_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5') RETURNING id",
            room_code, room_code
        )

    users = {}
    for label, role in [
        ("student", "student"),
        ("student2", "student"),
        ("council", "council_member"),
    ]:
        sid = f"P{random.randint(1000, 9999)}{label[:2].upper()}"
        uid = await auth_service.register_user(
            db_pool, sid, "1234", f"{label} ทดสอบ", sid, room_code, 1, role
        )
        users[label] = {
            "user_id": uid,
            "token": auth_service.create_access_token(uid),
            "room_id": room_id,
        }

    sid = f"P{random.randint(1000, 9999)}AD"
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
    return users


def _create_issue(client, world, *, destination="talk"):
    return client.post("/api/issues", json={
        "main_category": "report", "category": "complaint",
        "title": "เรื่องสำหรับ PIRI Board", "description": "รายละเอียด",
        "is_anonymous": False,
        "room_id": world["student"]["room_id"],
        "requested_destination": destination,
    }, headers={"Authorization": f"Bearer {world['student']['token']}"})


def _make_board(client, world, *, board_type="talk"):
    """สร้าง board ผ่าน flow จริง (issue → สภาอนุมัติ) → คืน board_id"""
    issue = _create_issue(client, world, destination=board_type)
    assert issue.status_code == 200, issue.text
    issue_id = issue.json()["id"]
    payload = {"board_type": board_type, "allow_comments": True}
    if board_type == "vote":
        payload["vote_choices"] = ["ตัวเลือก ก", "ตัวเลือก ข"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public", json=payload,
        headers={"Authorization": f"Bearer {world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text
    return res.json()["board_id"]


def _comment(client, world, board_id, body, parent_id=None):
    return _comment_as(client, world, board_id, body, actor="student", parent_id=parent_id)


def _comment_as(client, world, board_id, body, actor="student", parent_id=None):
    """คอมเมนต์โดย actor ที่ระบุ (default student) — ใช้กรณีต้องให้ "คนอื่น" เป็นเจ้าของคอมเมนต์"""
    payload = {"body": body}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    return client.post(
        f"/api/boards/{board_id}/comments", json=payload,
        headers={"Authorization": f"Bearer {world[actor]['token']}"},
    )


def _report(client, world, board_id, comment_id, reason="bullying", detail=None, actor="council"):
    payload = {"reason": reason}
    if detail:
        payload["detail"] = detail
    return client.post(
        f"/api/boards/{board_id}/comments/{comment_id}/report", json=payload,
        headers={"Authorization": f"Bearer {world[actor]['token']}"},
    )


def _hide(client, world, board_id, comment_id, reason="คอมเมนต์ไม่เหมาะสม"):
    return client.post(
        f"/api/boards/{board_id}/comments/{comment_id}/hide", json={"reason": reason},
        headers={"Authorization": f"Bearer {world['admin']['token']}"},
    )


def _unhide(client, world, board_id, comment_id):
    return client.post(
        f"/api/boards/{board_id}/comments/{comment_id}/unhide",
        headers={"Authorization": f"Bearer {world['admin']['token']}"},
    )


def _get(client, world, url, actor="student"):
    return client.get(url, headers={"Authorization": f"Bearer {world[actor]['token']}"})


# ==================== 1) report_comment ====================
@pytest.mark.asyncio
async def test_report_comment_success(client, board_world, db_pool):
    """นักเรียนแจ้งคอมเมนต์ไม่เหมาะสม → 200 + deep-DB (status open, reason, reporter) + audit"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "มีคนด่าเพื่อนผมครับ").json()["id"]

    res = _report(client, board_world, board_id, comment_id, reason="bullying", detail="ด่าว่าโง่ซ้ำๆ")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "open"

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT board_id, comment_id, reporter_id, reason, detail, status FROM piri_board_reports WHERE id = $1",
            data["id"]
        )
        assert row["board_id"] == board_id
        assert row["comment_id"] == comment_id
        assert row["reporter_id"] == board_world["council"]["user_id"]
        assert row["reason"] == "bullying"
        assert row["detail"] == "ด่าว่าโง่ซ้ำๆ"
        assert row["status"] == "open"
        audit = await conn.fetchrow(
            "SELECT new_values FROM audit_logs WHERE action = 'REPORT_COMMENT' ORDER BY created_at DESC LIMIT 1"
        )
        assert audit, "ต้องมี audit REPORT_COMMENT"
        assert json.loads(audit["new_values"])["comment_id"] == comment_id


@pytest.mark.asyncio
async def test_report_comment_duplicate_409(client, board_world, db_pool):
    """คนเดิมแจ้งคอมเมนต์เดิมซ้ำ → 409 (partial unique index)"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความไม่เหมาะสม").json()["id"]

    assert _report(client, board_world, board_id, comment_id).status_code == 200
    res = _report(client, board_world, board_id, comment_id)
    assert res.status_code == 409, res.text

    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval(
            "SELECT COUNT(*) FROM piri_board_reports WHERE comment_id = $1", comment_id
        )
        assert cnt == 1, "ต้องมีรายงานแค่ 1 รายการ (unique index กันซ้ำ)"


@pytest.mark.asyncio
async def test_report_comment_self_400(client, board_world):
    """แจ้งคอมเมนต์ของตัวเอง → 400 (กันป่วน/ดึงความสนใจ)"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "คอมเมนต์ของฉันเอง").json()["id"]

    res = _report(client, board_world, board_id, comment_id, actor="student")
    assert res.status_code == 400, res.text
    assert "ตัวเอง" in res.text


@pytest.mark.asyncio
async def test_report_comment_invalid_reason_422(client, board_world):
    """เหตุผลไม่อยู่ในหมวดที่กำหนด → 422 (Pydantic validator)"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]

    res = _report(client, board_world, board_id, comment_id, reason="hate")
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_report_comment_missing_comment_404(client, board_world):
    """คอมเมนต์ไม่อยู่ใน board (หรือไม่พบ) → 404"""
    board_id = _make_board(client, board_world, board_type="talk")
    res = _report(client, board_world, board_id, random.randint(90000, 99999))
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_report_comment_from_other_board_404(client, board_world):
    """คอมเมนต์ของ board อื่น → 404 (กัน cross-board — แจ้งผ่าน board ผิดแล้วไปลด counter ของอีก board)"""
    board_a = _make_board(client, board_world, board_type="talk")
    board_b = _make_board(client, board_world, board_type="talk")
    comment_a = _comment_as(client, board_world, board_a, "คอมเมนต์ใน board A", actor="student2").json()["id"]

    res = _report(client, board_world, board_b, comment_a)  # comment ของ A แจ้งผ่าน B
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_report_comment_soft_deleted_404(client, board_world, db_pool):
    """คอมเมนต์ที่ soft-delete แล้ว → 404 (ไม่ให้แจ้งซาก)"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment_as(client, board_world, board_id, "ข้อความ", actor="student2").json()["id"]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE piri_board_comments SET deleted_at = NOW() WHERE id = $1", comment_id)
    res = _report(client, board_world, board_id, comment_id)
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_report_comment_by_plain_student_success(client, board_world, db_pool):
    """หัวใจฟีเจอร์: นักเรียนธรรมดา (ไม่ใช่สภา) แจ้งคอมเมนต์ของคนอื่น → 200
    (adversarial review: ทุก test เดิมใช้ council/admin แจ้ง — ต้องพิสูจน์ว่า student แจ้งได้ด้วย)"""
    from services.board_moderation_service import MAX_OPEN_REPORTS_PER_USER
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment_as(client, board_world, board_id, "คอมเมนต์ของ student2", actor="student2").json()["id"]

    res = _report(client, board_world, board_id, comment_id, actor="student", reason="profanity")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "open"

    async with db_pool.acquire() as conn:
        reporter = await conn.fetchval(
            "SELECT reporter_id FROM piri_board_reports WHERE id = $1", res.json()["id"]
        )
        assert reporter == board_world["student"]["user_id"]


@pytest.mark.asyncio
async def test_report_comment_open_cap_blocks_flood(client, board_world):
    """กัน flood: user 1 คนแจ้งแบบ open ค้างเกิน MAX_OPEN_REPORTS_PER_USER ไม่ได้ → 400
    (adversarial review: ไม่มี cap → enumerate board/comment ใส่รายงานนับพันฝังคิวสภา)"""
    from services.board_moderation_service import MAX_OPEN_REPORTS_PER_USER
    board_id = _make_board(client, board_world, board_type="talk")
    # student2 เป็นเจ้าของคอมเมนต์ทุกอัน; student (ผู้แจ้ง) แจ้งทีละตัว
    comment_ids = []
    for _ in range(MAX_OPEN_REPORTS_PER_USER + 1):
        comment_ids.append(
            _comment_as(client, board_world, board_id, f"ข้อความ {_}", actor="student2").json()["id"]
        )
    for cid in comment_ids[:MAX_OPEN_REPORTS_PER_USER]:
        assert _report(client, board_world, board_id, cid, actor="student").status_code == 200
    res = _report(client, board_world, board_id, comment_ids[MAX_OPEN_REPORTS_PER_USER], actor="student")
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_report_comment_requires_auth(client, board_world):
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]
    res = client.post(f"/api/boards/{board_id}/comments/{comment_id}/report", json={"reason": "bullying"})
    assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_report_comment_hidden_board_404(client, board_world):
    """board ที่ถูกซ่อน → แจ้งไม่ได้ (404 เหมือน detail)"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]
    # สภา/แอดมินซ่อน board ก่อน
    res = client.post(
        f"/api/boards/{board_id}/hide", json={"reason": "สแปม"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text

    res = _report(client, board_world, board_id, comment_id)
    assert res.status_code == 404, res.text


# ==================== 2) hide_comment (subtree + counter) ====================
@pytest.mark.asyncio
async def test_hide_comment_subtree_decrements_counter_and_hides(client, board_world, db_pool):
    """ซ่อนคอมเมนต์หลัก → ลูก reply ซ่อนด้วย (subtree) + comment_count ลดตามจริง + หายจาก detail"""
    board_id = _make_board(client, board_world, board_type="talk")
    root = _comment(client, board_world, board_id, "คอมเมนต์หลักไม่เหมาะสม").json()["id"]
    reply = _comment(client, board_world, board_id, "reply ตาม", parent_id=root).json()["id"]
    _comment(client, board_world, board_id, "reply2 ตาม", parent_id=reply).json()["id"]
    # คอมเมนต์อื่น (ไม่ถูกซ่อน) — ต้องยังแสดง
    ok_id = _comment(client, board_world, board_id, "คอมเมนต์ปกติ").json()["id"]

    async with db_pool.acquire() as conn:
        before = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
    assert before == 4, "ก่อนซ่อนต้องมี 4 คอมเมนต์"

    res = _hide(client, board_world, board_id, root, reason="กลั่นแกล้ง")
    assert res.status_code == 200, res.text
    assert res.json()["hidden_count"] == 3, "ซ่อน root+reply+reply2 = 3 คอมเมนต์"

    # 🔍 Deep-DB: ทั้งต้นถูกซ่อน + counter ลด 3 + ตัวอื่นไม่โดน
    async with db_pool.acquire() as conn:
        hidden = await conn.fetchval(
            "SELECT COUNT(*) FROM piri_board_comments WHERE board_id = $1 AND is_hidden_by_admin = TRUE",
            board_id
        )
        assert hidden == 3
        root_row = await conn.fetchrow(
            "SELECT hidden_by, hidden_reason FROM piri_board_comments WHERE id = $1", root
        )
        assert root_row["hidden_by"] == board_world["admin"]["user_id"]
        assert root_row["hidden_reason"] == "กลั่นแกล้ง"
        after = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        assert after == before - 3, "comment_count ต้องลดตามจำนวนที่ซ่อนจริง"

    # detail ต้องไม่โชว์คอมเมนต์ที่ซ่อน (เห็นแค่คอมเมนต์ปกติ)
    detail = _get(client, board_world, f"/api/boards/{board_id}").json()
    comment_ids = [c["id"] for c in detail["comments"]]
    assert ok_id in comment_ids
    assert root not in comment_ids and reply not in comment_ids

    # audit HIDE_COMMENT
    async with db_pool.acquire() as conn:
        audit = await conn.fetchrow(
            "SELECT new_values FROM audit_logs WHERE action = 'HIDE_COMMENT' ORDER BY created_at DESC LIMIT 1"
        )
        assert audit
        assert json.loads(audit["new_values"])["hidden_comment_ids_count"] == 3


@pytest.mark.asyncio
async def test_hide_comment_already_hidden_409(client, board_world):
    """ซ่อนคอมเมนต์ที่ซ่อนอยู่แล้ว → 409 (กันลด counter ซ้ำ)"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]

    assert _hide(client, board_world, board_id, comment_id).status_code == 200
    res = _hide(client, board_world, board_id, comment_id)
    assert res.status_code == 409, res.text


@pytest.mark.asyncio
async def test_hide_comment_requires_council_403(client, board_world):
    """นักเรียนธรรมดา (ไม่มีอำนาจสภา/แอดมิน) ซ่อนคอมเมนต์ → 403"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]

    res = client.post(
        f"/api/boards/{board_id}/comments/{comment_id}/hide", json={"reason": "x"},
        headers={"Authorization": f"Bearer {board_world['student']['token']}"},
    )
    assert res.status_code == 403, res.text


# ==================== 3) unhide_comment ====================
@pytest.mark.asyncio
async def test_unhide_comment_restores_counter_and_visibility(client, board_world, db_pool):
    """ซ่อน → กลับมาแสดง (single comment) → comment_count เพิ่มคืน + โผล่ใน detail
    ⚠️ unhide เฉพาะตัวเดียว (ไม่ฟื้น subtree): unhide root → reply ยังซ่อน (กัน resurrection bug)"""
    board_id = _make_board(client, board_world, board_type="talk")
    root = _comment(client, board_world, board_id, "คอมเมนต์หลัก").json()["id"]
    reply = _comment(client, board_world, board_id, "reply", parent_id=root).json()["id"]

    _hide(client, board_world, board_id, root)   # ซ่อน subtree (root+reply) → count 0
    _unhide(client, board_world, board_id, root)  # unhide เฉพาะ root

    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        assert cnt == 1, "unhide root → เห็นแค่ root (reply ยังซ่อน)"
        reply_hidden = await conn.fetchval(
            "SELECT is_hidden_by_admin FROM piri_board_comments WHERE id = $1", reply
        )
        assert reply_hidden is True, "reply ต้องยังซ่อน (unhide ไม่ฟื้น subtree — กัน resurrection bug)"

    # unhide reply → ค่อยครบ
    _unhide(client, board_world, board_id, reply)
    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        assert cnt == 2

    detail = _get(client, board_world, f"/api/boards/{board_id}").json()
    root_node = next(c for c in detail["comments"] if c["id"] == root)
    assert root_node is not None, "root ต้องโผล่กลับมา"
    assert any(r["id"] == reply for r in root_node["replies"]), "reply ต้องซ้อนอยู่ใน root อีกครั้ง"


@pytest.mark.asyncio
async def test_unhide_comment_not_hidden_409(client, board_world):
    """unhide คอมเมนต์ที่ไม่ได้ถูกซ่อน → 409"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]
    res = _unhide(client, board_world, board_id, comment_id)
    assert res.status_code == 409, res.text


# ==================== 4) hide_board / unhide_board ====================
@pytest.mark.asyncio
async def test_hide_board_removes_from_feed_and_detail(client, board_world, db_pool):
    """ซ่อน board → หลุดจาก feed + detail 404 (ไม่มีข้อมูลรั่ว)"""
    board_id = _make_board(client, board_world, board_type="talk")
    _comment(client, board_world, board_id, "คอมเมนต์").json()["id"]

    res = client.post(
        f"/api/boards/{board_id}/hide", json={"reason": "สแปมบอร์ด"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "hidden"

    # feed ไม่มี + detail 404
    feed = _get(client, board_world, "/api/boards").json()
    assert board_id not in [b["id"] for b in feed["items"]]
    assert _get(client, board_world, f"/api/boards/{board_id}").status_code == 404

    async with db_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM piri_boards WHERE id = $1", board_id)
        assert status == "hidden"


@pytest.mark.asyncio
async def test_unhide_board_restores_feed(client, board_world):
    board_id = _make_board(client, board_world, board_type="talk")
    client.post(
        f"/api/boards/{board_id}/hide", json={"reason": "x"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    res = client.post(
        f"/api/boards/{board_id}/unhide",
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "active"

    feed = _get(client, board_world, "/api/boards").json()
    assert board_id in [b["id"] for b in feed["items"]]


@pytest.mark.asyncio
async def test_hide_board_requires_council_403(client, board_world):
    board_id = _make_board(client, board_world, board_type="talk")
    res = client.post(
        f"/api/boards/{board_id}/hide", json={"reason": "x"},
        headers={"Authorization": f"Bearer {board_world['student']['token']}"},
    )
    assert res.status_code == 403, res.text


# ==================== 5) resolve_report ====================
@pytest.mark.asyncio
async def test_resolve_report_hide_acts_on_comment_and_closes_reports(client, board_world, db_pool):
    """จัดการรายงานด้วย 'hide' → ซ่อนคอมเมนต์ (subtree + ลด counter) + ปิดรายงาน open ทั้งหมดที่จุดนั้น"""
    board_id = _make_board(client, board_world, board_type="talk")
    root = _comment(client, board_world, board_id, "คอมเมนต์โดนแจ้ง").json()["id"]
    reply = _comment(client, board_world, board_id, "reply", parent_id=root).json()["id"]

    r1 = _report(client, board_world, board_id, root, reason="bullying").json()["id"]
    r2 = _report(client, board_world, board_id, root, reason="profanity", actor="admin").json()["id"]

    async with db_pool.acquire() as conn:
        before = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
    assert before == 2

    res = client.post(
        f"/api/boards/reports/{r1}/resolve", json={"action": "hide", "note": "ยืนยันว่าผิดจริง"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "resolved"

    # 🔍 Deep-DB: ทั้งต้นซ่อน + counter ลด 2 + รายงานทั้ง 2 ปิด (resolved)
    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        assert cnt == before - 2
        hidden = await conn.fetchval(
            "SELECT COUNT(*) FROM piri_board_comments WHERE board_id = $1 AND is_hidden_by_admin = TRUE",
            board_id
        )
        assert hidden == 2
        open_reports = await conn.fetchval(
            "SELECT COUNT(*) FROM piri_board_reports WHERE comment_id = $1 AND status = 'open'",
            root
        )
        assert open_reports == 0
        r1_status = await conn.fetchval("SELECT status FROM piri_board_reports WHERE id = $1", r1)
        r2_status = await conn.fetchval("SELECT status FROM piri_board_reports WHERE id = $1", r2)
        assert r1_status == "resolved" and r2_status == "resolved"
        note = await conn.fetchval("SELECT resolution_note FROM piri_board_reports WHERE id = $1", r1)
        assert note == "ยืนยันว่าผิดจริง"


@pytest.mark.asyncio
async def test_resolve_report_dismiss_keeps_comment_visible(client, board_world, db_pool):
    """จัดการรายงานด้วย 'dismiss' → ปัดตก (ไม่ซ่อน) + รายงานปิด แต่คอมเมนต์ยังแสดง"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "คอมเมนต์ปกติ").json()["id"]
    r = _report(client, board_world, board_id, comment_id, reason="spam").json()["id"]

    res = client.post(
        f"/api/boards/reports/{r}/resolve", json={"action": "dismiss", "note": "ไม่เข้าข่าย"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "dismissed"

    async with db_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM piri_board_reports WHERE id = $1", r)
        assert status == "dismissed"
        hidden = await conn.fetchval(
            "SELECT is_hidden_by_admin FROM piri_board_comments WHERE id = $1", comment_id
        )
        assert hidden is False, "dismiss ต้องไม่ซ่อนคอมเมนต์"

    detail = _get(client, board_world, f"/api/boards/{board_id}").json()
    assert comment_id in [c["id"] for c in detail["comments"]]


@pytest.mark.asyncio
async def test_resolve_report_already_resolved_409(client, board_world):
    """รายงานที่ปิดแล้วจัดการซ้ำ → 409"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]
    r = _report(client, board_world, board_id, comment_id).json()["id"]

    client.post(
        f"/api/boards/reports/{r}/resolve", json={"action": "dismiss"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    res = client.post(
        f"/api/boards/reports/{r}/resolve", json={"action": "hide"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 409, res.text


@pytest.mark.asyncio
async def test_resolve_report_requires_council_403(client, board_world):
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]
    r = _report(client, board_world, board_id, comment_id).json()["id"]
    res = client.post(
        f"/api/boards/reports/{r}/resolve", json={"action": "hide"},
        headers={"Authorization": f"Bearer {board_world['student']['token']}"},
    )
    assert res.status_code == 403, res.text


@pytest.mark.asyncio
async def test_resolve_report_hide_closes_reports_on_replies(client, board_world, db_pool):
    """report บน reply (ลูกหลาน) ถูกปิดอัตโนมัติด้วย เมื่อ resolve ancestor ด้วย 'hide' (subtree)
    — ปิดช่องที่ report ของ reply ยังค้าง open อยู่ทั้งที่คอมเมนต์ถูกซ่อนไปแล้ว"""
    board_id = _make_board(client, board_world, board_type="talk")
    root = _comment(client, board_world, board_id, "root ที่ถูกแจ้ง").json()["id"]
    reply = _comment(client, board_world, board_id, "reply ที่ถูกแจ้งด้วย", parent_id=root).json()["id"]

    r_root = _report(client, board_world, board_id, root, reason="bullying").json()["id"]
    r_reply = _report(client, board_world, board_id, reply, reason="profanity", actor="admin").json()["id"]

    res = client.post(
        f"/api/boards/reports/{r_root}/resolve", json={"action": "hide"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text

    async with db_pool.acquire() as conn:
        reply_status = await conn.fetchval("SELECT status FROM piri_board_reports WHERE id = $1", r_reply)
        assert reply_status == "resolved", "report บน reply ต้องถูกปิด (resolved) ด้วย (อยู่ใน subtree ที่ซ่อน)"
        open_left = await conn.fetchval(
            "SELECT COUNT(*) FROM piri_board_reports WHERE comment_id = ANY(ARRAY[$1,$2]::int[]) AND status = 'open'",
            root, reply
        )
        assert open_left == 0


# ==================== 6) list_reports ====================
@pytest.mark.asyncio
async def test_list_reports_council_only(client, board_world):
    """คิวรายงาน: สภา/แอดมินเห็นได้, นักเรียนธรรมดา → 403"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]
    _report(client, board_world, board_id, comment_id)

    assert _get(client, board_world, "/api/boards/reports", actor="student").status_code == 403
    res = _get(client, board_world, "/api/boards/reports", actor="admin")
    assert res.status_code == 200, res.text
    assert len(res.json()["items"]) == 1
    item = res.json()["items"][0]
    assert item["board_id"] == board_id
    assert item["comment_body"] == "ข้อความ"
    assert item["reporter_name"] == "council ทดสอบ"
    assert item["reason"] == "bullying"


@pytest.mark.asyncio
async def test_list_reports_filter_status_and_search(client, board_world):
    """กรอง status + ค้นหา (board title / comment body)"""
    board_id = _make_board(client, board_world, board_type="talk")
    c1 = _comment(client, board_world, board_id, "คำหยาบคำแรก").json()["id"]
    c2 = _comment(client, board_world, board_id, "สแปมลิงก์").json()["id"]
    r1 = _report(client, board_world, board_id, c1, reason="profanity").json()["id"]
    _report(client, board_world, board_id, c2, reason="spam")

    # ปิด r1 ด้วย dismiss → เหลือ open 1 รายการ
    client.post(
        f"/api/boards/reports/{r1}/resolve", json={"action": "dismiss"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )

    # กรอง status=open → เหลือรายการ spam
    res = _get(client, board_world, "/api/boards/reports?status=open", actor="admin")
    assert res.status_code == 200, res.text
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["reason"] == "spam"

    # ค้นหา comment body → เจอคำหยาบ
    res = _get(client, board_world, "/api/boards/reports?q=สแปม", actor="admin")
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["comment_body"] == "สแปมลิงก์"


@pytest.mark.asyncio
async def test_list_reports_search_no_match_returns_empty(client, board_world):
    """ค้นหาที่ไม่ตรงอะไรเลย (q ไม่ match) → 200 + total=0 (ไม่ใช่ 500)
    regression: ตอนแรก fallback COUNT ลืม JOIN b/c → missing FROM-clause entry → 500 (adversarial review จับ)"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]
    _report(client, board_world, board_id, comment_id)

    res = _get(client, board_world, "/api/boards/reports?q=zzzzzzzzzz", actor="admin")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_reports_reason_filter_and_pagination(client, board_world):
    """กรอง reason + แบ่งหน้า (envelope) ของคิวรายงาน — regression gap จาก adversarial review"""
    board_id = _make_board(client, board_world, board_type="talk")
    c1 = _comment_as(client, board_world, board_id, "ข้อความ 1", actor="student2").json()["id"]
    c2 = _comment_as(client, board_world, board_id, "ข้อความ 2", actor="student2").json()["id"]
    c3 = _comment_as(client, board_world, board_id, "ข้อความ 3", actor="student2").json()["id"]
    _report(client, board_world, board_id, c1, reason="spam")
    _report(client, board_world, board_id, c2, reason="bullying")
    _report(client, board_world, board_id, c3, reason="profanity")

    # กรอง reason=spam → 1 รายการ
    res = _get(client, board_world, "/api/boards/reports?reason=spam", actor="admin")
    assert res.status_code == 200, res.text
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["reason"] == "spam"

    # pagination: limit=1 → total=3, pages=3, envelope ครบ
    res = _get(client, board_world, "/api/boards/reports?limit=1&offset=0", actor="admin")
    data = res.json()
    assert len(data["items"]) == 1
    assert data["total"] == 3
    assert data["pages"] == 3
    assert data["page"] == 1


# ==================== 7) 🔧 Counter integrity (หัวใจ Phase 5) ====================
@pytest.mark.asyncio
async def test_counter_matches_visible_comments_after_full_cycle(client, board_world, db_pool):
    """หลัง add/hide/unhide ทั้งวงจร comment_count ต้องตรงกับคอมเมนต์ที่ยังแสดงจริง (deep-DB)"""
    board_id = _make_board(client, board_world, board_type="talk")
    a = _comment(client, board_world, board_id, "คอมเมนต์ A").json()["id"]
    b = _comment(client, board_world, board_id, "คอมเมนต์ B", parent_id=a).json()["id"]
    c = _comment(client, board_world, board_id, "คอมเมนต์ C").json()["id"]

    _hide(client, board_world, board_id, a)      # ซ่อน A+B → เหลือ C
    _hide(client, board_world, board_id, c)      # ซ่อน C → เหลือ 0
    _unhide(client, board_world, board_id, a)    # กลับมา A (single) → เหลือ A
    _unhide(client, board_world, board_id, b)    # กลับมา B (reply) → เหลือ A+B

    async with db_pool.acquire() as conn:
        counter = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        actual = await conn.fetchval(
            """
            SELECT COUNT(*) FROM piri_board_comments
            WHERE board_id = $1 AND deleted_at IS NULL AND is_hidden_by_admin = FALSE
            """,
            board_id
        )
        assert counter == actual == 2, f"counter ({counter}) ต้องตรงกับจำนวนที่แสดงจริง ({actual})"


@pytest.mark.asyncio
async def test_counter_not_negative_when_drifted(client, board_world, db_pool):
    """ถ้า counter drift ต่ำกว่าความเป็นจริง → ซ่อนแล้วติดลบไม่ได้ (GREATEST กัน)"""
    board_id = _make_board(client, board_world, board_type="talk")
    comment_id = _comment(client, board_world, board_id, "ข้อความ").json()["id"]

    # แกล้งทำให้ counter ต่ำกว่าความเป็นจริง (จำลอง drift จากอดีต)
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE piri_boards SET comment_count = 0 WHERE id = $1", board_id)

    _hide(client, board_world, board_id, comment_id)

    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        assert cnt >= 0, "counter ต้องไม่ติดลบ (GREATEST(..., 0))"


@pytest.mark.asyncio
async def test_migration_reconcile_repairs_drifted_counters(client, board_world, db_pool):
    """Migration 008 reconcile: จำลอง drift (counter บวมจากยุคที่เพิ่มอย่างเดียว) → รัน reconcile SQL
    เดียวกับ migration → comment_count กลับมาตรงจำนวนที่แสดงจริง
    (adversarial review: reconcile ไม่เคยถูก test — ต้องพิสูจน์ว่า SQL ใช้ได้กับข้อมูล drift จริง)"""
    board_id = _make_board(client, board_world, board_type="talk")
    c1 = _comment(client, board_world, board_id, "คอมเมนต์ 1").json()["id"]
    _comment_as(client, board_world, board_id, "คอมเมนต์ 2", actor="student2").json()["id"]
    # ซ่อน c1 + soft-delete อีกตัว (จำลองข้อมูลเก่า) + แกล้ง counter ให้บวมเป็น 99
    _hide(client, board_world, board_id, c1)
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE piri_board_comments SET deleted_at = NOW() WHERE board_id = $1 AND id <> $2",
            board_id, c1
        )
        await conn.execute("UPDATE piri_boards SET comment_count = 99 WHERE id = $1", board_id)

        # รัน reconcile SQL เดียวกับ migration 008 (aggregate+JOIN — comment_count = นับที่ยังแสดงจริง)
        await conn.execute(
            """
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
            """
        )
        cnt = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        assert cnt == 0, f"reconcile ต้องลด 99 → 0 (คอมเมนต์ที่แสดงจริงเหลือ 0): {cnt}"
