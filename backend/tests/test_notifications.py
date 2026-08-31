"""
🔔 ระบบแจ้งเตือน (Notifications) — unread badge + read-receipt
=============================================================
ทดสอบทุก event → ตรวจ deep-DB ว่า notification แถวถูกสร้างให้ผู้รับที่ถูกต้อง
(read_at NULL = ยังไม่อ่าน) + self-exclusion + มาสก์ชื่อ anonymous + fan-out
+ unread-count แยกกลุ่ม + mark_read แบบต่างๆ + ไม่ cross-user leakage

Deep-DB verification ผ่าน db_pool (ไม่เชื่อ HTTP response อย่างเดียว — ตาม docs/rules/testing.md)
"""
import random

import pytest
import pytest_asyncio

from services import auth_service


@pytest_asyncio.fixture
async def notification_world(db_pool):
    """room (ม.5) + student/student2 + head (หัวหน้า) + vice (รอง) + level (ประธานระดับ)
    + council (สภา) + admin (สภา+is_admin) — ครบทุก receiver set"""
    room_code = f"บ.{random.randint(1, 90)}"
    async with db_pool.acquire() as conn:
        room_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5') RETURNING id",
            room_code, room_code
        )

    users = {}
    for label, role, no in [
        ("student", "student", 1),
        ("student2", "student", 2),
        ("head", "class_president", 3),
        ("vice", "vice_academic", 4),
        ("level", "level_president", 5),
        ("council", "council_member", 6),
    ]:
        sid = f"P{random.randint(1000, 9999)}{label[:2].upper()}"
        uid = await auth_service.register_user(
            db_pool, sid, "1234", f"{label} ทดสอบ", sid, room_code, no, role
        )
        users[label] = {
            "user_id": uid,
            "token": auth_service.create_access_token(uid),
            "room_id": room_id,
        }

    sid = f"P{random.randint(1000, 9999)}AD"
    uid = await auth_service.register_user(
        db_pool, sid, "1234", "แอดมิน ทดสอบ", sid, room_code, 7, "council_president"
    )
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE students SET is_admin = TRUE WHERE user_id = $1", uid)
    users["admin"] = {
        "user_id": uid,
        "token": auth_service.create_access_token(uid),
        "room_id": room_id,
    }
    return users


# ===================== helpers =====================

async def _notifs_async(db_pool, user_id, *, group_type=None, type=None):
    async with db_pool.acquire() as conn:
        where, params = ["user_id = $1"], [user_id]
        if group_type:
            params.append(group_type)
            where.append(f"group_type = ${len(params)}")
        if type:
            params.append(type)
            where.append(f"type = ${len(params)}")
        return await conn.fetch(
            f"SELECT * FROM notifications WHERE {' AND '.join(where)} ORDER BY id",
            *params
        )


def _create_issue(client, world, *, destination="normal", actor="student",
                  start_level="room", is_anonymous=False):
    res = client.post("/api/issues", json={
        "main_category": "report", "category": "complaint",
        "title": f"เรื่องแจ้งเตือน {random.randint(100, 999)}",
        "description": "รายละเอียด",
        "is_anonymous": is_anonymous,
        "room_id": world["student"]["room_id"],
        "start_level": start_level,
        "requested_destination": destination,
    }, headers={"Authorization": f"Bearer {world[actor]['token']}"})
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _accept(client, world, issue_id, actor="head", days=3):
    res = client.post(
        f"/api/issues/{issue_id}/accept", json={"estimated_days": days},
        headers={"Authorization": f"Bearer {world[actor]['token']}"},
    )
    assert res.status_code == 200, res.text


def _make_board(client, world, *, board_type="talk", actor="admin"):
    issue_id = _create_issue(client, world, destination=board_type)
    payload = {"board_type": board_type, "allow_comments": True}
    if board_type == "vote":
        payload["vote_choices"] = ["ตัวเลือก ก", "ตัวเลือก ข"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public", json=payload,
        headers={"Authorization": f"Bearer {world[actor]['token']}"},
    )
    assert res.status_code == 200, res.text
    return res.json()["board_id"]


def _comment_as(client, world, board_id, body, actor="student", parent_id=None):
    payload = {"body": body}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    res = client.post(
        f"/api/boards/{board_id}/comments", json=payload,
        headers={"Authorization": f"Bearer {world[actor]['token']}"},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _report(client, world, board_id, comment_id, actor="student", reason="bullying"):
    res = client.post(
        f"/api/boards/{board_id}/comments/{comment_id}/report",
        json={"reason": reason},
        headers={"Authorization": f"Bearer {world[actor]['token']}"},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


# ===================== 1) issue_new =====================

@pytest.mark.asyncio
async def test_issue_new_notifies_room_receivers(client, notification_world, db_pool):
    """student แจ้งเรื่องระดับห้อง → head + vice ได้ issue_received; สภา/ประธานระดับ/คนอื่น 0"""
    issue_id = _create_issue(client, notification_world, destination="normal")

    for label in ("head", "vice"):
        rows = await _notifs_async(db_pool, notification_world[label]["user_id"])
        assert len(rows) == 1, f"{label} ต้องได้ 1 notification"
        assert rows[0]["group_type"] == "issue_received"
        assert rows[0]["type"] == "issue_new"
        assert rows[0]["entity_type"] == "issue"
        assert rows[0]["entity_id"] == issue_id
        assert rows[0]["read_at"] is None

    for label in ("council", "level", "admin", "student", "student2"):
        rows = await _notifs_async(db_pool, notification_world[label]["user_id"])
        assert len(rows) == 0, f"{label} ไม่ควรได้ notification"


@pytest.mark.asyncio
async def test_issue_new_anonymous_masks_reporter_name(client, notification_world, db_pool):
    """เรื่อง anonymous → actor_name='ไม่ระบุชื่อ' และ body ไม่มีชื่อจริง"""
    issue_id = _create_issue(client, notification_world, is_anonymous=True)
    rows = await _notifs_async(db_pool, notification_world["head"]["user_id"])
    assert len(rows) == 1
    assert rows[0]["actor_name"] == "ไม่ระบุชื่อ"
    assert "student ทดสอบ" not in rows[0]["body"]
    assert "ไม่ระบุชื่อ" in rows[0]["body"]


@pytest.mark.asyncio
async def test_issue_new_public_request_notifies_council(client, notification_world, db_pool):
    """เรื่องขอเผยแพร่สาธารณะ (vote) → ตรงไปสภา: council + admin ได้; head ไม่ได้"""
    issue_id = _create_issue(client, notification_world, destination="vote")

    for label in ("council", "admin"):
        rows = await _notifs_async(db_pool, notification_world[label]["user_id"])
        assert len(rows) == 1, f"{label} ต้องได้ notification"
        assert rows[0]["group_type"] == "issue_received"
        assert rows[0]["entity_id"] == issue_id

    for label in ("head", "vice"):
        rows = await _notifs_async(db_pool, notification_world[label]["user_id"])
        assert len(rows) == 0, f"{label} ไม่ควรได้ (เรื่องตรงไปสภาแล้ว)"


@pytest.mark.asyncio
async def test_issue_new_start_level_notifies_level_president(client, notification_world, db_pool):
    """เรื่องเริ่มที่ระดับ level (admin สร้าง) → ประธานระดับได้ issue_received"""
    issue_id = _create_issue(client, notification_world, start_level="level", actor="admin")
    rows = await _notifs_async(db_pool, notification_world["level"]["user_id"])
    assert len(rows) == 1
    assert rows[0]["group_type"] == "issue_received"
    assert rows[0]["entity_id"] == issue_id


# ===================== 2) issue_update (accept/escalate/resolve/reject) =====================

@pytest.mark.asyncio
async def test_accept_issue_notifies_reporter_only(client, notification_world, db_pool):
    """head รับงาน → student (ผู้แจ้ง) ได้ issue_mine; head เองไม่โดน (self-exclusion)"""
    issue_id = _create_issue(client, notification_world)
    _accept(client, notification_world, issue_id, actor="head")

    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"])
    assert len(stu) == 1
    assert stu[0]["group_type"] == "issue_mine"
    assert stu[0]["type"] == "issue_update"
    assert stu[0]["entity_id"] == issue_id
    assert "รับ" in stu[0]["body"]

    # head ได้ issue_new ตอนสร้างเรื่อง (ถูกต้อง) แต่ต้องไม่มี issue_update จากการรับงานเอง
    head = await _notifs_async(db_pool, notification_world["head"]["user_id"], type="issue_update")
    assert len(head) == 0, "ผู้รับงานเองไม่ควรโดนแจ้ง (self-exclusion)"


@pytest.mark.asyncio
async def test_escalate_notifies_reporter_and_level_receiver(client, notification_world, db_pool):
    """head ส่งต่อ → student ได้ issue_mine (ส่งต่อ) + ประธานระดับได้ issue_new"""
    issue_id = _create_issue(client, notification_world)
    _accept(client, notification_world, issue_id, actor="head")
    res = client.post(
        f"/api/issues/{issue_id}/escalate", json={"reason": "เกินความสามารถ"},
        headers={"Authorization": f"Bearer {notification_world['head']['token']}"},
    )
    assert res.status_code == 200, res.text

    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="issue_update")
    assert any("ส่งต่อ" in r["body"] for r in stu), "ต้องมี notification การส่งต่อ"

    lvl = await _notifs_async(db_pool, notification_world["level"]["user_id"], type="issue_new")
    assert len(lvl) == 1, "ประธานระดับต้องโดนแจ้งเรื่องใหม่ (ส่งต่อจาก room)"


@pytest.mark.asyncio
async def test_resolve_notifies_reporter(client, notification_world, db_pool):
    issue_id = _create_issue(client, notification_world)
    _accept(client, notification_world, issue_id, actor="head")
    res = client.post(
        f"/api/issues/{issue_id}/resolve", json={"reason": "แก้เสร็จ"},
        headers={"Authorization": f"Bearer {notification_world['head']['token']}"},
    )
    assert res.status_code == 200, res.text

    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="issue_update")
    assert any("เสร็จสิ้น" in r["body"] for r in stu), "ต้องมี notification การปิดเรื่อง"


@pytest.mark.asyncio
async def test_reject_notifies_reporter(client, notification_world, db_pool):
    """head ปัดตก (reject) → student ได้แจ้ง; student กดยกเลิกเอง → ไม่มี notification"""
    issue_id = _create_issue(client, notification_world)
    _accept(client, notification_world, issue_id, actor="head")
    res = client.post(
        f"/api/issues/{issue_id}/cancel", json={"reason": "นอกขอบเขต"},
        headers={"Authorization": f"Bearer {notification_world['head']['token']}"},
    )
    assert res.status_code == 200, res.text
    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="issue_update")
    assert any("ปัดตก" in r["body"] for r in stu), "ต้องมี notification การปัดตก"


@pytest.mark.asyncio
async def test_self_cancel_no_notification(client, notification_world, db_pool):
    """student กดยกเลิกเรื่องตัวเอง → ไม่มี notification (self-guard)"""
    issue_id = _create_issue(client, notification_world)
    res = client.post(
        f"/api/issues/{issue_id}/cancel", json={"reason": "แจ้งผิด"},
        headers={"Authorization": f"Bearer {notification_world['student']['token']}"},
    )
    assert res.status_code == 200, res.text
    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"])
    assert len(stu) == 0


# ===================== 3) issue_comment =====================

@pytest.mark.asyncio
async def test_issue_comment_notifies_reporter_and_assignee(client, notification_world, db_pool):
    """vice คอมเมนต์ → student (ผู้แจ้ง) ได้ issue_mine + head (ผู้รับ) ได้ issue_received; vice 0"""
    issue_id = _create_issue(client, notification_world)
    _accept(client, notification_world, issue_id, actor="head")

    res = client.post(
        f"/api/issues/{issue_id}/comments", json={"body": "คอมเมนต์ทดสอบ"},
        headers={"Authorization": f"Bearer {notification_world['vice']['token']}"},
    )
    assert res.status_code == 200, res.text

    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="issue_comment")
    assert len(stu) == 1 and stu[0]["group_type"] == "issue_mine"

    head = await _notifs_async(db_pool, notification_world["head"]["user_id"], type="issue_comment")
    assert len(head) == 1 and head[0]["group_type"] == "issue_received"

    # vice ได้ issue_new ตอนสร้างเรื่อง (ถูกต้อง) แต่ต้องไม่มี issue_comment จากตัวเอง
    vice = await _notifs_async(db_pool, notification_world["vice"]["user_id"], type="issue_comment")
    assert len(vice) == 0, "คนคอมเมนต์เองไม่โดนแจ้ง"


@pytest.mark.asyncio
async def test_anonymous_reporter_comment_masks_name(client, notification_world, db_pool):
    """เรื่อง anonymous + ผู้แจ้งคอมเมนต์เอง → notification ของผู้รับงานต้องไม่มีชื่อจริง
    (adversarial fix: เดิม commenter name ส่งตรง notification ให้ผู้รับงานเห็นชื่อผู้แจ้งทันที)"""
    issue_id = _create_issue(client, notification_world, is_anonymous=True)
    _accept(client, notification_world, issue_id, actor="head")

    res = client.post(
        f"/api/issues/{issue_id}/comments", json={"body": "คอมเมนต์จากผู้แจ้งเอง"},
        headers={"Authorization": f"Bearer {notification_world['student']['token']}"},
    )
    assert res.status_code == 200, res.text

    head = await _notifs_async(db_pool, notification_world["head"]["user_id"], type="issue_comment")
    assert len(head) == 1
    assert head[0]["actor_name"] == "ไม่ระบุชื่อ"
    assert "student ทดสอบ" not in head[0]["body"]


# ===================== 4) board_new fan-out =====================

@pytest.mark.asyncio
async def test_board_new_fans_out_all_active_users(client, notification_world, db_pool):
    """approve เป็น board → ทุก active user ได้ board_new 1 แถว ยกเว้นผู้ที่อนุมัติ (admin)"""
    _make_board(client, notification_world, board_type="talk", actor="admin")

    for label in ("student", "student2", "head", "vice", "level", "council"):
        rows = await _notifs_async(db_pool, notification_world[label]["user_id"], type="board_new")
        assert len(rows) == 1, f"{label} ต้องได้ board_new 1 แถว"

    admin_rows = await _notifs_async(db_pool, notification_world["admin"]["user_id"], type="board_new")
    assert len(admin_rows) == 0, "ผู้ที่อนุมัติเองไม่ควรได้ board_new (self-exclusion)"


@pytest.mark.asyncio
async def test_board_new_dedup_multi_room_user(client, notification_world, db_pool):
    """user ที่มี students หลายห้อง (ย้ายห้อง/หลายบทบาท) → ได้ board_new แค่ 1 แถว
    (adversarial fix: notify_fanout เดิมไม่มี DISTINCT → badge บอร์ดป่องเกินจริง)"""
    async with db_pool.acquire() as conn:
        room_code = await conn.fetchval(
            "SELECT room_code FROM rooms WHERE id = $1", notification_world["student"]["room_id"]
        )
    room2_code = f"บ.{random.randint(91, 99)}"
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5')",
            room2_code, room2_code
        )

    # ลงทะเบียน user เดียวใน 2 ห้อง (student_id ต่าง → students 2 rows ผูก user_id เดียว)
    sid = f"P{random.randint(1000, 9999)}MX"
    uid = await auth_service.register_user(db_pool, sid, "1234", "สองห้อง ทดสอบ", sid, room_code, 1, "student")
    uid2 = await auth_service.register_user(db_pool, sid, "1234", "สองห้อง ทดสอบ", f"{sid}2", room2_code, 2, "student")
    assert uid == uid2, "register เดิม user เดียวต้องได้ user_id เดียว"

    async with db_pool.acquire() as conn:
        rows_cnt = await conn.fetchval(
            "SELECT COUNT(*) FROM students WHERE user_id = $1 AND deleted_at IS NULL", uid
        )
    assert rows_cnt == 2, "ต้องมี students 2 rows (2 ห้อง)"

    _make_board(client, notification_world, board_type="talk", actor="admin")

    rows = await _notifs_async(db_pool, uid, type="board_new")
    assert len(rows) == 1, "แม้มี 2 ห้องต้องได้ board_new แค่ 1 แถว (DISTINCT)"


# ===================== 5) board_reply / board_comment =====================

@pytest.mark.asyncio
async def test_board_reply_notifies_parent_author(client, notification_world, db_pool):
    """student2 reply คอมเมนต์ของ student → student ได้ board_reply; student2 ไม่โดน"""
    board_id = _make_board(client, notification_world, board_type="talk")
    c1 = _comment_as(client, notification_world, board_id, "คอมเมนต์แรก", actor="student")
    _comment_as(client, notification_world, board_id, "ตอบกลับ", actor="student2", parent_id=c1)

    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="board_reply")
    assert len(stu) == 1, "เจ้าของคอมเมนต์ต้นทางต้องได้แจ้ง"
    assert stu[0]["title"] == "มีผู้ตอบกลับความคิดเห็นของคุณ"
    assert stu[0]["board_id"] == board_id

    s2 = await _notifs_async(db_pool, notification_world["student2"]["user_id"], type="board_reply")
    assert len(s2) == 0, "คนตอบกลับเองไม่โดนแจ้ง"


@pytest.mark.asyncio
async def test_board_top_level_comment_notifies_board_author(client, notification_world, db_pool):
    """คอมเมนต์ top-level → เจ้าของบอร์ด (student ผู้แจ้งเรื่อง) ได้แจ้ง"""
    board_id = _make_board(client, notification_world, board_type="talk")
    _comment_as(client, notification_world, board_id, "คอมเมนต์บนบอร์ด", actor="student2")

    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="board_reply")
    assert len(stu) == 1 and stu[0]["title"] == "มีคอมเมนต์ใหม่ในกระทู้ของคุณ"
    assert stu[0]["board_id"] == board_id


@pytest.mark.asyncio
async def test_board_author_comment_self_no_notify(client, notification_world, db_pool):
    """เจ้าของบอร์ดคอมเมนต์เอง → ไม่โดนแจ้ง (self-guard)"""
    board_id = _make_board(client, notification_world, board_type="talk")
    _comment_as(client, notification_world, board_id, "เจ้าของพูดเอง", actor="student")

    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="board_reply")
    assert len(stu) == 0


# ===================== 6) board_hidden =====================

@pytest.mark.asyncio
async def test_board_hidden_notifies_board_author(client, notification_world, db_pool):
    board_id = _make_board(client, notification_world, board_type="talk")
    res = client.post(
        f"/api/boards/{board_id}/hide", json={"reason": "เนื้อหาไม่เหมาะสม"},
        headers={"Authorization": f"Bearer {notification_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text

    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="board_hidden")
    assert len(stu) == 1 and "ถูกซ่อน" in stu[0]["body"]
    assert stu[0]["board_id"] == board_id


# ===================== 7) report_new / report_actioned =====================

@pytest.mark.asyncio
async def test_report_new_notifies_council_excluding_reporter(client, notification_world, db_pool):
    board_id = _make_board(client, notification_world, board_type="talk")
    c1 = _comment_as(client, notification_world, board_id, "คอมเมนต์โดนแจ้ง", actor="student2")
    _report(client, notification_world, board_id, c1, actor="student")

    for label in ("council", "admin"):
        rows = await _notifs_async(db_pool, notification_world[label]["user_id"], type="report_new")
        assert len(rows) == 1, f"{label} ต้องได้แจ้งรายงานใหม่"
    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="report_new")
    assert len(stu) == 0, "ผู้แจ้งเองไม่โดนแจ้งรายงานใหม่"


@pytest.mark.asyncio
async def test_report_actioned_notifies_report_reporter(client, notification_world, db_pool):
    board_id = _make_board(client, notification_world, board_type="talk")
    c1 = _comment_as(client, notification_world, board_id, "คอมเมนต์โดนแจ้ง", actor="student2")
    report_id = _report(client, notification_world, board_id, c1, actor="student")

    res = client.post(
        f"/api/boards/reports/{report_id}/resolve", json={"action": "dismiss", "note": "ไม่เข้าข่าย"},
        headers={"Authorization": f"Bearer {notification_world['admin']['token']}"},
    )
    assert res.status_code == 200, res.text

    stu = await _notifs_async(db_pool, notification_world["student"]["user_id"], type="report_actioned")
    assert len(stu) == 1 and "จัดการ" in stu[0]["body"]


# ===================== 8) unread-count / list / mark_read =====================

@pytest.mark.asyncio
async def test_unread_counts_grouping(client, notification_world, db_pool):
    """ปนหลายเหตุการณ์ → GET /unread-count นับแยกกลุ่มถูกต้อง"""
    issue_id = _create_issue(client, notification_world)          # head: issue_received=1
    _accept(client, notification_world, issue_id, actor="head")    # student: issue_mine=1
    board_id = _make_board(client, notification_world, board_type="talk")  # ทุกคน board=1 (ยกเว้น admin)

    # head: issue_received(1) + board(1)
    res = client.get("/api/notifications/unread-count",
                     headers={"Authorization": f"Bearer {notification_world['head']['token']}"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["counts"]["issue_received"] == 1
    assert data["counts"]["board"] == 1
    assert data["counts"]["issue_mine"] == 0
    assert data["total"] == 2

    # student: issue_mine(1) + board(1)
    res = client.get("/api/notifications/unread-count",
                     headers={"Authorization": f"Bearer {notification_world['student']['token']}"})
    data = res.json()
    assert data["counts"]["issue_mine"] == 1
    assert data["counts"]["board"] == 1
    assert data["total"] == 2

    # admin: ถูก exclude จาก board_new (ผู้ที่อนุมัติเอง) แต่เป็นสภา → ได้ issue_received
    # ตอนสร้างเรื่องขอ board (destination talk → ตรงไปสภา)
    res = client.get("/api/notifications/unread-count",
                     headers={"Authorization": f"Bearer {notification_world['admin']['token']}"})
    data = res.json()
    assert data["counts"]["issue_received"] == 1
    assert data["counts"]["board"] == 0
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_notifications_paginated(client, notification_world, db_pool):
    issue_id = _create_issue(client, notification_world)
    _accept(client, notification_world, issue_id, actor="head")

    res = client.get("/api/notifications",
                     headers={"Authorization": f"Bearer {notification_world['student']['token']}"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["group_type"] == "issue_mine"
    assert data["items"][0]["read_at"] is None
    assert data["items"][0]["entity_type"] == "issue"

    # filter unread_only + group
    res = client.get("/api/notifications?unread_only=true&group_type=issue_mine",
                     headers={"Authorization": f"Bearer {notification_world['student']['token']}"})
    assert res.json()["total"] == 1


@pytest.mark.asyncio
async def test_mark_read_variants(client, notification_world, db_pool):
    """mark อ่านแบบ: ids / entity_type+entity_id (issue) / board_id / read_all
    (accept ซ้ำไม่ได้ → สร้าง issue ใหม่ทุกขั้น)"""
    stu_uid = notification_world["student"]["user_id"]

    # (a) mark อ่านเฉพาะ id → เคลียร์แค่แถวนั้น
    i1 = _create_issue(client, notification_world)
    _accept(client, notification_world, i1, actor="head")      # student: issue_mine (issue i1)
    i1_rows = await _notifs_async(db_pool, stu_uid, type="issue_update")
    assert len(i1_rows) == 1
    res = client.post("/api/notifications/read", json={"ids": [i1_rows[0]["id"]]},
                      headers={"Authorization": f"Bearer {notification_world['student']['token']}"})
    assert res.status_code == 200 and res.json()["updated"] == 1
    counts = client.get("/api/notifications/unread-count",
                        headers={"Authorization": f"Bearer {notification_world['student']['token']}"}).json()
    assert counts["counts"]["issue_mine"] == 0

    # (b) mark โดย board_id → เคลียร์ notification ของ board นั้น
    board_id = _make_board(client, notification_world, board_type="talk")  # student: board
    counts = client.get("/api/notifications/unread-count",
                        headers={"Authorization": f"Bearer {notification_world['student']['token']}"}).json()
    assert counts["counts"]["board"] == 1
    res = client.post("/api/notifications/read", json={"board_id": board_id},
                      headers={"Authorization": f"Bearer {notification_world['student']['token']}"})
    assert res.json()["updated"] == 1
    counts = client.get("/api/notifications/unread-count",
                        headers={"Authorization": f"Bearer {notification_world['student']['token']}"}).json()
    assert counts["counts"]["board"] == 0

    # (c) entity_type+entity_id เคลียร์เฉพาะกลุ่ม issue ของเรื่องนั้น
    i2 = _create_issue(client, notification_world)
    _accept(client, notification_world, i2, actor="head")
    res = client.post("/api/notifications/read",
                      json={"entity_type": "issue", "entity_id": i2},
                      headers={"Authorization": f"Bearer {notification_world['student']['token']}"})
    assert res.json()["updated"] == 1

    # (d) read_all เคลียร์ทุกอย่าง
    i3 = _create_issue(client, notification_world)
    _accept(client, notification_world, i3, actor="head")
    res = client.post("/api/notifications/read", json={"read_all": True},
                      headers={"Authorization": f"Bearer {notification_world['student']['token']}"})
    assert res.json()["updated"] == 1
    counts = client.get("/api/notifications/unread-count",
                        headers={"Authorization": f"Bearer {notification_world['student']['token']}"}).json()
    assert counts["total"] == 0

    # deep-DB: ทุกแถว read_at ไม่ใช่ NULL
    async with db_pool.acquire() as conn:
        unread = await conn.fetchval(
            "SELECT COUNT(*) FROM notifications WHERE user_id = $1 AND read_at IS NULL", stu_uid
        )
    assert unread == 0


@pytest.mark.asyncio
async def test_mark_read_without_criteria_400(client, notification_world):
    """POST /read ไม่ระบุอะไรเลย → 400 (กันเผลอเคลียร์ทุกอย่าง)"""
    res = client.post("/api/notifications/read", json={},
                      headers={"Authorization": f"Bearer {notification_world['student']['token']}"})
    assert res.status_code == 400, res.text


@pytest.mark.asyncio
async def test_no_cross_user_leakage(client, notification_world, db_pool):
    """A กับ B แยกกัน: รายการ/นับ/การ mark-read ไม่ปนกัน"""
    issue_id = _create_issue(client, notification_world)   # head ได้ issue_received
    _accept(client, notification_world, issue_id, actor="head")  # student ได้ issue_mine

    # student2 ไม่เห็นอะไรของคนอื่น
    res = client.get("/api/notifications",
                     headers={"Authorization": f"Bearer {notification_world['student2']['token']}"})
    assert res.json()["total"] == 0
    res = client.get("/api/notifications/unread-count",
                     headers={"Authorization": f"Bearer {notification_world['student2']['token']}"})
    assert res.json()["total"] == 0

    # student2 กด read_all → ไม่กระทบ head/student
    res = client.post("/api/notifications/read", json={"read_all": True},
                      headers={"Authorization": f"Bearer {notification_world['student2']['token']}"})
    assert res.json()["updated"] == 0

    head_unread = await _notifs_async(db_pool, notification_world["head"]["user_id"])
    assert all(r["read_at"] is None for r in head_unread)
    stu_unread = await _notifs_async(db_pool, notification_world["student"]["user_id"])
    assert all(r["read_at"] is None for r in stu_unread)
