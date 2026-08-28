"""
PIRI Boards — Phase 3: Board Service & API (PIRI Vote + PIRI Talk)
==================================================================
ทดสอบ 4 ฟีเจอร์ใน board_service (routers/boards.py):
1. list_public_boards — feed ที่ active, ไม่มี pyramid visibility, กรองประเภท/ค้นหา/แบ่งหน้า
2. get_board_detail   — vote: choices + my_vote_choice_id; talk: comments แบบ threaded
3. submit_vote        — โหวต 1 เสียง/board (โหวตซ้ำ → 409 จาก UniqueViolationError; soft-delete แล้วโหวตใหม่ได้)
4. add_comment        — คอมเมนต์/รีพลาย (talk + allow_comments เท่านั้น)

Deep-DB verification ผ่าน db_pool (ไม่เชื่อ HTTP response อย่างเดียว — ตาม docs/rules/testing.md)
"""
import json
import random

import pytest
import pytest_asyncio

from services import auth_service
from services.board_service import MAX_REPLY_DEPTH, MAX_DISPLAY_DEPTH


@pytest_asyncio.fixture
async def board_world(db_pool):
    """สร้าง room + users ครบชุด: student (ผู้โหวต/คอมเมนต์), council, admin (อนุมัติ board)"""
    room_code = f"บ.{random.randint(1, 90)}"
    async with db_pool.acquire() as conn:
        room_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5') RETURNING id",
            room_code, room_code
        )

    users = {}
    for label, role in [
        ("student", "student"),
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


def _create_issue(client, world, *, destination="talk", title="เรื่องสำหรับ PIRI Board",
                  desc="รายละเอียด", anonymous=False):
    """ผู้แจ้ง (student) ขอเผยแพร่สาธารณะ — vote/talk"""
    return client.post("/api/issues", json={
        "main_category": "report", "category": "complaint",
        "title": title, "description": desc,
        "is_anonymous": anonymous,
        "room_id": world["student"]["room_id"],
        "requested_destination": destination,
    }, headers={"Authorization": f"Bearer {world['student']['token']}"})


def _make_board(client, world, *, board_type="vote", choices=None, allow_comments=True,
                title="เรื่องสำหรับ PIRI Board", desc="รายละเอียด"):
    """สร้าง board ผ่าน flow จริง (issue → สภาอนุมัติ) → คืน (issue_id, board_id)
    ทำทุก test ที่อยากได้ board เริ่มต้น (reuse — อย่าทำซ้ำเงื่อนไขในแต่ละ test)"""
    issue = _create_issue(client, world, destination=board_type, title=title, desc=desc)
    assert issue.status_code == 200, issue.text
    issue_id = issue.json()["id"]

    payload = {"board_type": board_type, "allow_comments": allow_comments}
    if board_type == "vote":
        payload["vote_choices"] = choices or ["ตัวเลือก ก", "ตัวเลือก ข", "ตัวเลือก ค"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public", json=payload,
        headers={"Authorization": f"Bearer {world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text
    return issue_id, res.json()["board_id"]


def _vote(client, world, board_id, choice_id):
    return client.post(
        f"/api/boards/{board_id}/vote", json={"choice_id": choice_id},
        headers={"Authorization": f"Bearer {world['student']['token']}"},
    )


def _comment(client, world, board_id, body, parent_id=None):
    payload = {"body": body}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    return client.post(
        f"/api/boards/{board_id}/comments", json=payload,
        headers={"Authorization": f"Bearer {world['student']['token']}"},
    )


def _get(client, world, url):
    return client.get(url, headers={"Authorization": f"Bearer {world['student']['token']}"})


# ==================== 1) list_public_boards ====================
@pytest.mark.asyncio
async def test_list_public_boards_active_only_and_no_pyramid(client, board_world, db_pool):
    """feed คืน board ที่ active เท่านั้น (soft-delete แล้วหลุด) + student ธรรมดาเห็นได้ (ไม่มี pyramid)"""
    issue1, board1 = _make_board(client, board_world, board_type="vote")
    _, board2 = _make_board(client, board_world, board_type="talk")

    # soft-delete board1 → ต้องไม่โผล่ใน feed
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE piri_boards SET deleted_at = NOW() WHERE id = $1", board1)

    res = _get(client, board_world, "/api/boards")
    assert res.status_code == 200, res.text
    data = res.json()
    ids = [b["id"] for b in data["items"]]
    assert board2 in ids and board1 not in ids, f"board ที่ soft-delete ต้องไม่โผล่: {ids}"
    assert data["total"] == 1
    # feed item ต้องมี field การ์ดครบ
    b = data["items"][0]
    assert b["board_type"] == "talk"
    assert b["comment_count"] == 0
    assert b["author_name"] == "student ทดสอบ"  # ไม่ anonymous → โชว์ชื่อผู้แจ้ง

    # deep-DB: total นับเฉพาะ active
    async with db_pool.acquire() as conn:
        n_active = await conn.fetchval(
            "SELECT count(*) FROM piri_boards WHERE status='active' AND deleted_at IS NULL")
    assert data["total"] == n_active


@pytest.mark.asyncio
async def test_list_public_boards_pagination(client, board_world):
    """limit/offset แบ่งหน้า: total นับครบ, page/pages ถูกต้อง"""
    for _ in range(3):
        _make_board(client, board_world, board_type="talk")

    res = _get(client, board_world, "/api/boards?limit=2")
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["page"] == 1 and data["pages"] == 2
    first_page_ids = [b["id"] for b in data["items"]]

    res2 = _get(client, board_world, "/api/boards?limit=2&offset=2")
    data2 = res2.json()
    assert len(data2["items"]) == 1
    assert data2["page"] == 2
    # หน้า 2 ต้องเป็น board ที่เหลือ (ไม่ซ้ำกับหน้า 1)
    assert data2["items"][0]["id"] not in first_page_ids

    # หน้าเลย total (offset=10) → items ว่าง แต่ total/pages ยังถูก (fallback COUNT(*) ใน service)
    res3 = _get(client, board_world, "/api/boards?limit=2&offset=10")
    data3 = res3.json()
    assert data3["items"] == []
    assert data3["total"] == 3
    assert data3["pages"] == 2


@pytest.mark.asyncio
async def test_list_public_boards_filter_by_type(client, board_world):
    """board_type=vote → ได้เฉพาะ board แบบ vote"""
    _, vote_id = _make_board(client, board_world, board_type="vote")
    _make_board(client, board_world, board_type="talk")

    res = _get(client, board_world, "/api/boards?board_type=vote")
    data = res.json()
    assert all(b["board_type"] == "vote" for b in data["items"])
    assert vote_id in [b["id"] for b in data["items"]]
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_public_boards_search(client, board_world):
    """q ค้นหา title/description (escape wildcard)"""
    _make_board(client, board_world, board_type="talk", title="ป้ายชื่อห้องหาย ห้อง 3/1")
    _make_board(client, board_world, board_type="talk", title="ไฟเสียหน้าอาคารเรียน")

    res = _get(client, board_world, "/api/boards?q=ป้ายชื่อ")
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "ป้ายชื่อห้องหาย ห้อง 3/1"

    # ค้นหาคำที่ไม่มีใน board ใด → ว่าง
    res2 = _get(client, board_world, "/api/boards?q=zzzzzz")
    assert res2.json()["total"] == 0

    # 🔍 wildcard ต้องถูก escape — q='%' ไม่ควรจับคู่ทุก board (ต้องหนี % กลายเป็นตัวอักษรจริง)
    res3 = _get(client, board_world, "/api/boards?q=%25")  # % URL-encoded
    assert res3.json()["total"] == 0, "q='%' ต้องไม่เจอ board ใด (escape wildcard แล้ว)"


@pytest.mark.asyncio
async def test_list_public_boards_anonymous_hides_author(client, board_world, db_pool):
    """board ที่ผู้แจ้งขอ anonymous → author_name เป็น None (ไม่รั่วชื่อ)"""
    issue = _create_issue(client, board_world, destination="talk", anonymous=True)
    issue_id = issue.json()["id"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "talk"},
        headers={"Authorization": f"Bearer {board_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text

    feed = _get(client, board_world, "/api/boards").json()
    anon = [b for b in feed["items"] if b["id"] == res.json()["board_id"]][0]
    assert anon["is_anonymous"] is True
    assert anon["author_name"] is None
    assert anon["author_id"] is None, "board anonymous ต้องไม่รั่ว author_id (กัน deanonymization)"

    # detail ก็ไม่รั่วเหมือนกัน (รวม my_vote_choice_id เป็น None)
    detail = _get(client, board_world, f"/api/boards/{res.json()['board_id']}").json()
    assert detail["author_id"] is None and detail["author_name"] is None

    # deep-DB: is_anonymous ถูกตั้งจริงตอน approve
    async with db_pool.acquire() as conn:
        db_flag = await conn.fetchval(
            "SELECT is_anonymous FROM piri_boards WHERE id = $1", res.json()["board_id"])
    assert db_flag is True


@pytest.mark.asyncio
async def test_boards_require_auth(client, board_world):
    """ทุก endpoint ของ boards ต้องล็อกอิน (401 ถ้าไม่มี token)"""
    assert client.get("/api/boards").status_code == 401
    assert client.get("/api/boards/1").status_code == 401
    assert client.post("/api/boards/1/vote", json={"choice_id": 1}).status_code == 401
    assert client.post("/api/boards/1/comments", json={"body": "hi"}).status_code == 401


# ==================== 2) get_board_detail ====================
@pytest.mark.asyncio
async def test_get_board_detail_vote(client, board_world):
    """vote board: choices ครบ + total_votes=0 + my_vote_choice_id=None (ยังไม่โหวต)"""
    _, board_id = _make_board(client, board_world, board_type="vote")
    res = _get(client, board_world, f"/api/boards/{board_id}")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["board_type"] == "vote"
    assert data["allow_comments"] is True
    assert data["total_votes"] == 0
    assert data["my_vote_choice_id"] is None
    assert [c["choice_text"] for c in data["choices"]] == ["ตัวเลือก ก", "ตัวเลือก ข", "ตัวเลือก ค"]
    assert [c["sort_order"] for c in data["choices"]] == [0, 1, 2]
    assert all(c["vote_count"] == 0 for c in data["choices"])


@pytest.mark.asyncio
async def test_get_board_detail_talk_threaded_comments(client, board_world, db_pool):
    """talk board: comments เป็น tree (reply ซ้อน reply) + is_edited=False"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    a = _comment(client, board_world, board_id, "คอมเมนต์หลัก ก").json()["id"]
    b = _comment(client, board_world, board_id, "รีพลาย ข", parent_id=a).json()["id"]
    _comment(client, board_world, board_id, "รีพลายลึก ค", parent_id=b)

    res = _get(client, board_world, f"/api/boards/{board_id}")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["comment_count"] == 3
    roots = data["comments"]
    assert len(roots) == 1 and roots[0]["id"] == a
    assert roots[0]["commenter_name"] == "student ทดสอบ"
    assert len(roots[0]["replies"]) == 1 and roots[0]["replies"][0]["id"] == b
    assert roots[0]["replies"][0]["replies"][0]["body"] == "รีพลายลึก ค"

    # deep-DB: comment_count ใน piri_boards อัปเดตจริง
    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        n_rows = await conn.fetchval(
            "SELECT count(*) FROM piri_board_comments WHERE board_id = $1 AND deleted_at IS NULL", board_id)
    assert cnt == 3 == n_rows


@pytest.mark.asyncio
async def test_get_board_detail_soft_deleted_comment_skipped(client, board_world, db_pool):
    """คอมเมนต์ที่ soft delete แล้วไม่โผล่ใน detail"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    cid = _comment(client, board_world, board_id, "จะถูกลบ").json()["id"]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE piri_board_comments SET deleted_at = NOW() WHERE id = $1", cid)

    data = _get(client, board_world, f"/api/boards/{board_id}").json()
    assert data["comments"] == []


@pytest.mark.asyncio
async def test_get_board_detail_hidden_404(client, board_world, db_pool):
    """board ที่ admin ซ่อน (status='hidden') → 404 (ไม่รั่วข้อมูล)"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE piri_boards SET status = 'hidden' WHERE id = $1", board_id)
    assert _get(client, board_world, f"/api/boards/{board_id}").status_code == 404


@pytest.mark.asyncio
async def test_get_board_detail_missing_404(client, board_world):
    assert _get(client, board_world, f"/api/boards/{random.randint(90000, 99999)}").status_code == 404


# ==================== 3) submit_vote ====================
@pytest.mark.asyncio
async def test_submit_vote_success(client, board_world, db_pool):
    """โหวตสำเร็จ → vote_count+1 (deep-DB) + audit SUBMIT_VOTE + detail เห็น my_vote"""
    _, board_id = _make_board(client, board_world, board_type="vote")
    choices = _get(client, board_world, f"/api/boards/{board_id}").json()["choices"]
    cid = choices[0]["id"]

    res = _vote(client, board_world, board_id, cid)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "ok"
    assert res.json()["choice_text"] == "ตัวเลือก ก"

    # 🔍 Deep-DB
    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT vote_count FROM piri_vote_choices WHERE id = $1", cid)
        assert cnt == 1
        vote = await conn.fetchrow(
            "SELECT board_id, choice_id, user_id FROM piri_votes WHERE board_id = $1 AND user_id = $2",
            board_id, board_world["student"]["user_id"]
        )
        assert vote is not None and vote["choice_id"] == cid
        audit = await conn.fetchrow(
            "SELECT new_values FROM audit_logs WHERE action = 'SUBMIT_VOTE' ORDER BY created_at DESC LIMIT 1"
        )
        assert audit, "ต้องมี audit SUBMIT_VOTE"
        assert json.loads(audit["new_values"])["choice_id"] == cid

    # detail หลังโหวต → my_vote_choice_id + total_votes
    data = _get(client, board_world, f"/api/boards/{board_id}").json()
    assert data["my_vote_choice_id"] == cid
    assert data["total_votes"] == 1


@pytest.mark.asyncio
async def test_submit_vote_duplicate_409(client, board_world, db_pool):
    """โหวตซ้ำ board เดียว → 409 (UniqueViolationError) + vote_count ไม่เพิ่มซ้ำ"""
    _, board_id = _make_board(client, board_world, board_type="vote")
    choices = _get(client, board_world, f"/api/boards/{board_id}").json()["choices"]
    cid = choices[0]["id"]

    assert _vote(client, board_world, board_id, cid).status_code == 200
    second = _vote(client, board_world, board_id, cid)
    assert second.status_code == 409, second.text
    assert "โหวต" in second.text

    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT vote_count FROM piri_vote_choices WHERE id = $1", cid)
        n_votes = await conn.fetchval(
            "SELECT count(*) FROM piri_votes WHERE board_id = $1 AND user_id = $2",
            board_id, board_world["student"]["user_id"]
        )
    assert cnt == 1, "vote_count ต้องไม่เพิ่มซ้ำตอน 409"
    assert n_votes == 1, "ต้องมี vote เดียว"


@pytest.mark.asyncio
async def test_submit_vote_revote_after_soft_delete(client, board_world, db_pool):
    """โหวต → soft-delete vote → โหวตใหม่ได้ (partial unique กันเฉพาะ row active)"""
    _, board_id = _make_board(client, board_world, board_type="vote")
    choices = _get(client, board_world, f"/api/boards/{board_id}").json()["choices"]
    c1, c2 = choices[0]["id"], choices[1]["id"]

    assert _vote(client, board_world, board_id, c1).status_code == 200
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE piri_votes SET deleted_at = NOW() WHERE board_id = $1 AND user_id = $2",
            board_id, board_world["student"]["user_id"]
        )
    res = _vote(client, board_world, board_id, c2)
    assert res.status_code == 200, res.text

    async with db_pool.acquire() as conn:
        cnt2 = await conn.fetchval("SELECT vote_count FROM piri_vote_choices WHERE id = $1", c2)
    assert cnt2 == 1
    # my_vote เปลี่ยนไป choice ใหม่
    data = _get(client, board_world, f"/api/boards/{board_id}").json()
    assert data["my_vote_choice_id"] == c2


@pytest.mark.asyncio
async def test_submit_vote_talk_board_400(client, board_world):
    """โหวต talk board → 400 (board ไม่ใช่แบบโหวต)"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    res = _vote(client, board_world, board_id, 1)
    assert res.status_code == 400, res.text
    assert "โหวต" in res.text


@pytest.mark.asyncio
async def test_submit_vote_choice_from_other_board_404(client, board_world):
    """choice ของ board อื่น → 404 (กันโหวตข้าม board)"""
    _, board_a = _make_board(client, board_world, board_type="vote")
    _, board_b = _make_board(client, board_world, board_type="vote")
    choices_b = _get(client, board_world, f"/api/boards/{board_b}").json()["choices"]
    res = _vote(client, board_world, board_a, choices_b[0]["id"])
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_submit_vote_missing_board_404(client, board_world):
    res = _vote(client, board_world, random.randint(90000, 99999), 1)
    assert res.status_code == 404, res.text


# ==================== 4) add_comment ====================
@pytest.mark.asyncio
async def test_add_comment_success(client, board_world, db_pool):
    """คอมเมนต์สำเร็จ → comment_count+1 (deep-DB) + audit ADD_COMMENT + response ครบ"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    res = _comment(client, board_world, board_id, "สวัสดีครับ สภานักเรียน")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["body"] == "สวัสดีครับ สภานักเรียน"
    assert data["parent_comment_id"] is None
    assert data["commenter_name"] == "student ทดสอบ"

    # 🔍 Deep-DB
    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        assert cnt == 1
        row = await conn.fetchrow(
            "SELECT board_id, user_id FROM piri_board_comments WHERE id = $1", data["id"]
        )
        assert row["board_id"] == board_id
        assert row["user_id"] == board_world["student"]["user_id"]
        audit = await conn.fetchrow(
            "SELECT new_values FROM audit_logs WHERE action = 'ADD_COMMENT' ORDER BY created_at DESC LIMIT 1"
        )
        assert audit, "ต้องมี audit ADD_COMMENT"
        assert json.loads(audit["new_values"])["body"] == "สวัสดีครับ สภานักเรียน"


@pytest.mark.asyncio
async def test_add_comment_reply(client, board_world, db_pool):
    """reply (parent_id) → parent_comment_id ถูกตั้ง + อยู่ใน thread"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    a = _comment(client, board_world, board_id, "คำถาม").json()["id"]
    res = _comment(client, board_world, board_id, "คำตอบ", parent_id=a)
    assert res.status_code == 200, res.text
    assert res.json()["parent_comment_id"] == a

    async with db_pool.acquire() as conn:
        pid = await conn.fetchval("SELECT parent_comment_id FROM piri_board_comments WHERE id = $1", res.json()["id"])
    assert pid == a


@pytest.mark.asyncio
async def test_add_comment_vote_board_400(client, board_world):
    """คอมเมนต์ board แบบ vote → 400 (เฉพาะ PIRI Talk)"""
    _, board_id = _make_board(client, board_world, board_type="vote")
    res = _comment(client, board_world, board_id, "คอมเมนต์บนโหวต")
    assert res.status_code == 400, res.text
    assert "Talk" in res.text


@pytest.mark.asyncio
async def test_add_comment_when_comments_closed_403(client, board_world, db_pool):
    """board ปิดคอมเมนต์ (allow_comments=False) → 403 + comment_count ไม่เพิ่ม"""
    _, board_id = _make_board(client, board_world, board_type="talk", allow_comments=False)
    res = _comment(client, board_world, board_id, "มาคอมเมนต์บน board ที่ปิด")
    assert res.status_code == 403, res.text

    async with db_pool.acquire() as conn:
        cnt = await conn.fetchval("SELECT comment_count FROM piri_boards WHERE id = $1", board_id)
        assert cnt == 0


@pytest.mark.asyncio
async def test_add_comment_invalid_parent_404(client, board_world):
    """reply ต่อ parent ที่ไม่มี/ถูกลบ → 404"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    res = _comment(client, board_world, board_id, "รีพลายหาคน", parent_id=random.randint(90000, 99999))
    assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_add_comment_missing_board_404(client, board_world):
    res = _comment(client, board_world, random.randint(90000, 99999), "ไม่เจอ board")
    assert res.status_code == 404, res.text


# ==================== เพิ่มตาม adversarial review ====================
@pytest.mark.asyncio
async def test_list_public_boards_visible_to_user_in_other_room(client, board_world, db_pool):
    """การ์ดสำคัญ: 'no pyramid visibility' — ผู้ใช้ห้องอื่น (คนละห้องกับผู้เขียน) ต้องเห็น board ได้
    (ถ้า service เผลอจำกัดแค่ห้องเดียวกัน test นี้จะจับได้)"""
    _, board_id = _make_board(client, board_world, board_type="talk")

    # สร้างผู้ใช้ห้องอื่น (คนละ room_code กับ board_world)
    other_room = f"บ.{random.randint(91, 200)}"
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.4')",
            other_room, other_room
        )
    sid = f"Q{random.randint(1000, 9999)}OX"
    uid = await auth_service.register_user(
        db_pool, sid, "1234", "นักเรียนต่างห้อง", sid, other_room, 1, "student"
    )
    token = auth_service.create_access_token(uid)

    # ผู้ใช้ห้องอื่นเห็น board ของห้องคนอื่นใน feed + detail
    res = client.get("/api/boards", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    assert board_id in [b["id"] for b in res.json()["items"]], "ห้องอื่นต้องเห็น board สาธารณะ (ไม่มี pyramid)"
    assert res.json()["total"] >= 1

    res2 = client.get(f"/api/boards/{board_id}", headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 200, res2.text
    assert res2.json()["id"] == board_id


@pytest.mark.asyncio
async def test_get_board_detail_orphaned_reply_promoted_after_parent_soft_delete(client, board_world, db_pool):
    """reply ที่ parent โดน soft delete → ย้ายขึ้น root (ยังแสดงต่อ ไม่หายทั้งต้น) + parent ไม่รั่ว"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    a = _comment(client, board_world, board_id, "parent จะถูกลบ").json()["id"]
    b = _comment(client, board_world, board_id, "ลูกที่ต้องอยู่รอด", parent_id=a).json()["id"]

    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE piri_board_comments SET deleted_at = NOW() WHERE id = $1", a)

    data = _get(client, board_world, f"/api/boards/{board_id}").json()
    roots = [c for c in data["comments"] if c["parent_comment_id"] is None]
    assert len(roots) == 1 and roots[0]["id"] == b, "ลูกของ parent ที่ถูกลบต้องขึ้นเป็น root"
    assert all(c["id"] != a for c in data["comments"]), "parent ที่ soft delete แล้วต้องไม่โผล่"


@pytest.mark.asyncio
async def test_submit_vote_change_choice_409(client, board_world, db_pool):
    """เปลี่ยนตัวเลือก (โหวต c1 แล้วมาโหวต c2) → 409 เช่นกัน (partial unique board+user) + vote_count ไม่เพี้ยน"""
    _, board_id = _make_board(client, board_world, board_type="vote")
    choices = _get(client, board_world, f"/api/boards/{board_id}").json()["choices"]
    c1, c2 = choices[0]["id"], choices[1]["id"]

    assert _vote(client, board_world, board_id, c1).status_code == 200
    res = _vote(client, board_world, board_id, c2)
    assert res.status_code == 409, res.text
    assert "โหวต" in res.text

    async with db_pool.acquire() as conn:
        cnt1 = await conn.fetchval("SELECT vote_count FROM piri_vote_choices WHERE id = $1", c1)
        cnt2 = await conn.fetchval("SELECT vote_count FROM piri_vote_choices WHERE id = $1", c2)
    assert cnt1 == 1 and cnt2 == 0, "เปลี่ยนตัวเลือกตอนโหวตซ้ำ ต้องไม่เพิ่ม vote_count"


# ==================== กัน recursive Pydantic overflow (reply chain ลึกเกิน) ====================
@pytest.mark.asyncio
async def test_add_comment_reply_depth_limited(client, board_world, db_pool):
    """สร้าง reply ต่อ parent ที่ chain ลึกถึง MAX_REPLY_DEPTH แล้ว → 400 (write-side guard)
    (ถ้าไม่มี guard นี้ chain ลึก ~256 ชั้นจะทำ BoardDetailOut crash = DoS)"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    uid = board_world["student"]["user_id"]

    # สร้าง chain ตรง DB ให้ยาว MAX_REPLY_DEPTH (ลึก 1..MAX_REPLY_DEPTH)
    async with db_pool.acquire() as conn:
        pid = None
        for _ in range(MAX_REPLY_DEPTH):
            pid = await conn.fetchval(
                "INSERT INTO piri_board_comments (board_id, parent_comment_id, user_id, body) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                board_id, pid, uid, f"chain-{_}"
            )
        depth_of_last = await conn.fetchval(
            """
            WITH RECURSIVE chain(depth, cid) AS (
                SELECT 1, $1::integer
                UNION ALL
                SELECT chain.depth + 1, c.parent_comment_id
                FROM piri_board_comments c JOIN chain ON c.id = chain.cid
                WHERE c.parent_comment_id IS NOT NULL AND chain.depth < 100
            )
            SELECT COALESCE(MAX(depth), 0) FROM chain
            """, pid
        )
    assert depth_of_last == MAX_REPLY_DEPTH, "chain ต้องลึกถึง MAX_REPLY_DEPTH จริง"

    # reply ต่อ deepest (parent_depth == MAX_REPLY_DEPTH) → 400
    res = _comment(client, board_world, board_id, "ลึกเกินไป", parent_id=pid)
    assert res.status_code == 400, res.text
    assert "ลึก" in res.text

    # แต่ reply ต่อ parent หนึ่งชั้นก่อน (ลึก MAX_REPLY_DEPTH-1) ยังพอได้ → 200
    async with db_pool.acquire() as conn:
        prev = await conn.fetchval(
            "SELECT parent_comment_id FROM piri_board_comments WHERE id = $1", pid)
    ok = _comment(client, board_world, board_id, "ยังพอได้", parent_id=prev)
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_get_board_detail_deep_chain_bounded_does_not_crash(client, board_world, db_pool):
    """tree ที่ส่ง client ถูกพับไม่ให้ลึกเกิน MAX_DISPLAY_DEPTH — chain 60 ชั้น (เกิน guard) ยัง GET 200
    (กัน recursive Pydantic overflow — adversarial review: ~256 ชั้น → ValidationError 500)"""
    _, board_id = _make_board(client, board_world, board_type="talk")
    uid = board_world["student"]["user_id"]

    async with db_pool.acquire() as conn:
        pid = None
        for _ in range(60):
            pid = await conn.fetchval(
                "INSERT INTO piri_board_comments (board_id, parent_comment_id, user_id, body) "
                "VALUES ($1, $2, $3, $4) RETURNING id",
                board_id, pid, uid, f"deep-{_}"
            )

    res = _get(client, board_world, f"/api/boards/{board_id}")
    assert res.status_code == 200, res.text
    data = res.json()

    # ความลึก tree สูงสุดต้องไม่เกิน MAX_DISPLAY_DEPTH
    def max_depth(nodes: list, d: int = 0) -> int:
        if not nodes:
            return d
        return max(max_depth(n["replies"], d + 1) for n in nodes)

    # max_depth วัดแบบ 1-indexed (root=1) ส่วน service ใช้ 0-indexed → bound = MAX_DISPLAY_DEPTH + 1
    assert max_depth(data["comments"]) <= MAX_DISPLAY_DEPTH + 1, "reply ลึกเกินต้องถูกพับ ไม่ crash"
    # คอมเมนต์ไม่หาย (60 อัน ยังครบ)
    def count_nodes(nodes: list) -> int:
        return len(nodes) + sum(count_nodes(n["replies"]) for n in nodes)

    assert count_nodes(data["comments"]) == 60, "ทุกคอมเมนต์ยังต้องถูกส่งกลับ (แค่พับความลึก)"
