# === GET /api/issues/summary — สรุปเรื่องที่ฉันแจ้ง (หน้า Home/Welcome) ===
# {total_issues, by_status[6 zero-fill], recent[<=5]}
import random

import pytest
import pytest_asyncio

from services import auth_service


@pytest_asyncio.fixture
async def summary_world(db_pool):
    """สร้างห้อง + นักเรียนผู้แจ้ง 2 คน (คนแรก = subject ของ summary)"""
    room_code = f"ม.4/{random.randint(100, 999)}"
    async with db_pool.acquire() as conn:
        room_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1, $2, 'ม.4') RETURNING id",
            room_code,
            room_code,
        )

    users = {}
    for label, role in [("me", "student"), ("other", "student")]:
        sid = f"S{random.randint(1000, 9999)}{label}"
        uid = await auth_service.register_user(
            db_pool, sid, "1234", f"{label} ผู้แจ้ง", sid, room_code, 1, role
        )
        users[label] = {
            "user_id": uid,
            "token": auth_service.create_access_token(uid),
            "room_id": room_id,
        }
    return users


def _create(client, who, *, title="เรื่องทดสอบ", main_category="report", category="complaint"):
    return client.post(
        "/api/issues",
        json={
            "main_category": main_category,
            "category": category,
            "title": title,
            "description": "รายละเอียดเรื่องทดสอบ",
            "is_anonymous": False,
            "room_id": who["room_id"],
        },
        headers={"Authorization": f"Bearer {who['token']}"},
    )


async def _set_status(db_pool, issue_id: int, status: str):
    """ย้ายสถานะเรื่องตรง ๆ (deep DB) — กำหนดชุดสถานะให้ deterministic"""
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE issues SET status = $1 WHERE id = $2", status, issue_id)


@pytest.mark.asyncio
async def test_my_issue_summary_counts(client, db_pool, summary_world):
    """จำนวนรวม + by_status ครบ 6 (zero-fill) — เฉพาะเรื่องของฉัน ไม่นับคนอื่น/ที่ถูกลบ"""
    me, other = summary_world["me"], summary_world["other"]

    # เรื่องของฉัน: กำหนดสถานะชัด ๆ (pending, in_progress, resolved, rejected)
    mine_ids = {}
    for label, status in [
        ("pending", "pending"),
        ("in_progress", "in_progress"),
        ("resolved", "resolved"),
        ("rejected", "rejected"),
    ]:
        res = _create(client, me, title=f"ของฉัน {label}")
        assert res.status_code == 200
        mine_ids[label] = res.json()["id"]
        await _set_status(db_pool, mine_ids[label], status)

    # เรื่องที่ถูกลบ (soft delete) → ต้องไม่นับ
    res = _create(client, me, title="ของฉัน ถูกลบ")
    deleted_id = res.json()["id"]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE issues SET deleted_at = NOW() WHERE id = $1", deleted_id)

    # เรื่องของคนอื่น 2 เรื่อง → ต้องไม่นับ
    for n in range(2):
        assert _create(client, other, title=f"ของคนอื่น {n}").status_code == 200

    res = client.get("/api/issues/summary", headers={"Authorization": f"Bearer {me['token']}"})
    assert res.status_code == 200
    body = res.json()

    assert body["total_issues"] == 4
    by_status = {s["status"]: s["count"] for s in body["by_status"]}
    assert by_status == {
        "pending": 1,
        "in_progress": 1,
        "escalated": 0,
        "rejected": 1,
        "resolved": 1,
        "cancelled": 0,
    }

    # Deep DB verify: นับจริงจาก DB ต้องตรง
    async with db_pool.acquire() as conn:
        db_total = await conn.fetchval(
            "SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL AND reporter_id = $1",
            me["user_id"],
        )
        assert db_total == body["total_issues"]
        db_resolved = await conn.fetchval(
            "SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL AND reporter_id = $1 AND status = 'resolved'",
            me["user_id"],
        )
        assert db_resolved == by_status["resolved"]


@pytest.mark.asyncio
async def test_my_issue_summary_recent(client, db_pool, summary_world):
    """recent = เรื่องของฉันล่าสุด (เรียง created_at DESC) ไม่เกิน 5"""
    me = summary_world["me"]
    ids = []
    for n in range(3):
        res = _create(client, me, title=f"ลำดับ {n}")
        assert res.status_code == 200
        ids.append(res.json()["id"])

    res = client.get("/api/issues/summary", headers={"Authorization": f"Bearer {me['token']}"})
    assert res.status_code == 200
    body = res.json()

    assert len(body["recent"]) == 3
    # สร้างทีหลัง → ขึ้นก่อน (created_at DESC + id DESC tiebreak)
    assert [i["id"] for i in body["recent"]] == list(reversed(ids))
    assert all({"id", "title", "status", "main_category", "created_at"} <= set(i) for i in body["recent"])

    # Deep DB verify: ลำดับล่าสุดใน DB ตรงกับ recent
    async with db_pool.acquire() as conn:
        db_recent = await conn.fetch(
            """
            SELECT id FROM issues
            WHERE deleted_at IS NULL AND reporter_id = $1
            ORDER BY created_at DESC, id DESC
            LIMIT 5
            """,
            me["user_id"],
        )
    assert [r["id"] for r in db_recent] == [i["id"] for i in body["recent"]]


@pytest.mark.asyncio
async def test_my_issue_summary_requires_auth(client):
    """ไม่มี token → 401"""
    res = client.get("/api/issues/summary")
    assert res.status_code == 401
