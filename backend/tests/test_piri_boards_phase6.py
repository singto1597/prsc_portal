"""
PIRI Boards — Phase 6: View-count dedup (กัน F5 ปั่นยอด)
=========================================================
ทดสอบ piri_board_views (board_id,user_id PK) + เงื่อนไข VIEW_DEDUP_WINDOW:
- user 1 คน ดู board ซ้ำภายใน window → view_count นับแค่ 1 (refresh รัวๆ ไม่ปั่นยอด)
- เลย window แล้วดูใหม่ → นับเพิ่ม (คนเดิมดูจริงครั้งถัดไป)
- คนละคนดู → นับแยกคน

Deep-DB verification ผ่าน db_pool (ตาม docs/rules/testing.md)
"""
import random

import pytest
import pytest_asyncio

from services import auth_service


@pytest_asyncio.fixture
async def board_world(db_pool):
    """room + users: student + council (ดู/อนุมัติ board)"""
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
    return users


def _make_board(client, world):
    """สร้าง talk board ผ่าน flow จริง (issue → สภาอนุมัติ) → คืน board_id"""
    issue = client.post("/api/issues", json={
        "main_category": "report", "category": "complaint",
        "title": "เรื่องสำหรับ PIRI Board", "description": "รายละเอียด",
        "is_anonymous": False,
        "room_id": world["student"]["room_id"],
        "requested_destination": "talk",
    }, headers={"Authorization": f"Bearer {world['student']['token']}"})
    assert issue.status_code == 200, issue.text
    issue_id = issue.json()["id"]
    res = client.post(
        f"/api/issues/{issue_id}/approve-to-public",
        json={"board_type": "talk", "allow_comments": True},
        headers={"Authorization": f"Bearer {world['council']['token']}"},
    )
    assert res.status_code == 200, res.text
    return res.json()["board_id"]


def _get(client, world, url, actor="student"):
    return client.get(url, headers={"Authorization": f"Bearer {world[actor]['token']}"})


@pytest.mark.asyncio
async def test_view_count_dedup_same_user_within_window(client, board_world, db_pool):
    """user เดียวดู board ซ้ำติดๆ (ภายใน window) → view_count นับแค่ 1 (กัน F5 ปั่นยอด)"""
    board_id = _make_board(client, board_world)

    assert _get(client, board_world, f"/api/boards/{board_id}").status_code == 200
    assert _get(client, board_world, f"/api/boards/{board_id}").status_code == 200
    assert _get(client, board_world, f"/api/boards/{board_id}").status_code == 200

    async with db_pool.acquire() as conn:
        vc = await conn.fetchval("SELECT view_count FROM piri_boards WHERE id = $1", board_id)
        assert vc == 1, f"refresh รัวๆ ภายใน window ต้องนับแค่ 1 ครั้ง: {vc}"


@pytest.mark.asyncio
async def test_view_count_counts_again_after_window(client, board_world, db_pool):
    """เลย window (10 นาที) แล้วดูใหม่ → นับเพิ่ม (คนเดิมดูจริงครั้งถัดไป)"""
    board_id = _make_board(client, board_world)
    _get(client, board_world, f"/api/boards/{board_id}")

    # เลื่อน viewed_at ให้เก่าเกิน window (จำลองเวลาผ่านไป)
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE piri_board_views SET viewed_at = NOW() - INTERVAL '11 minutes' WHERE board_id = $1",
            board_id
        )
        vc = await conn.fetchval("SELECT view_count FROM piri_boards WHERE id = $1", board_id)
        assert vc == 1

    _get(client, board_world, f"/api/boards/{board_id}")
    async with db_pool.acquire() as conn:
        vc = await conn.fetchval("SELECT view_count FROM piri_boards WHERE id = $1", board_id)
        assert vc == 2, f"เลย window แล้วดูใหม่ต้องนับเพิ่ม: {vc}"


@pytest.mark.asyncio
async def test_view_count_separate_users_count_separately(client, board_world, db_pool):
    """คนละคนดูบอร์ดเดียวกัน → นับแยก (คนละ row ใน piri_board_views)"""
    board_id = _make_board(client, board_world)

    _get(client, board_world, f"/api/boards/{board_id}", actor="student")
    _get(client, board_world, f"/api/boards/{board_id}", actor="council")
    _get(client, board_world, f"/api/boards/{board_id}", actor="council")

    async with db_pool.acquire() as conn:
        vc = await conn.fetchval("SELECT view_count FROM piri_boards WHERE id = $1", board_id)
        assert vc == 2, f"student 1 + council 1 (ซ้ำไม่นับ) = 2: {vc}"
        rows = await conn.fetchval(
            "SELECT COUNT(*) FROM piri_board_views WHERE board_id = $1", board_id
        )
        assert rows == 2, "ต้องมี 2 rows (student + council)"
