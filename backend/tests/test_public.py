# === Public API Tests: Landing Page (stats / resolved-cases / announcements) ===
# เส้นทางทั้งหมดอยู่ที่ /api/v1/public/* — ไม่ต้องล็อกอิน
import random

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def public_world(db_pool):
    """สร้างโลกทดสอบ: ห้อง ม.4 + นักเรียน + เรื่อง resolved 1 + pending 1 + ประกาศ 2"""
    room_code = f"ม.4/{random.randint(100, 999)}"
    async with db_pool.acquire() as conn:
        room_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1, $2, 'ม.4') RETURNING id",
            room_code,
            room_code,
        )
        reporter_id = await conn.fetchval(
            "INSERT INTO users (username, password_hash, full_name) VALUES ($1, $2, $3) RETURNING id",
            f"pub_stu_{random.randint(10000, 99999)}",
            "x",
            "นักเรียน ม.4",
        )
        # เรื่องที่ resolve แล้ว (มี resolved_at + status_history note + assignee)
        resolved_id = await conn.fetchval(
            """
            INSERT INTO issues (room_id, main_category, category, title, description,
                                reporter_id, reporter_room_id, current_assignee_role,
                                status, priority, resolved_at, created_at)
            VALUES ($1, 'suggestion', 'สิ่งแวดล้อม', $2, $3, $4, $1, 'council_member',
                    'resolved', 'high', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 days')
            RETURNING id
            """,
            room_id,
            "แก้ไขห้องน้ำหญิงชั้น 2",
            "ท่อตันและกลิ่นรบกวน",
            reporter_id,
        )
        await conn.execute(
            """
            INSERT INTO issue_status_history (issue_id, status, changed_by, note)
            VALUES ($1, 'resolved', $2, $3)
            """,
            resolved_id,
            reporter_id,
            "ซ่อมท่อและทำความสะอาดเรียบร้อยแล้ว",
        )
        # เรื่องที่ยัง pending — ต้องไม่โผล่ใน resolved-cases
        await conn.fetchval(
            """
            INSERT INTO issues (room_id, main_category, category, title, description,
                                reporter_id, reporter_room_id, status, priority)
            VALUES ($1, 'wellbeing', 'สวัสดิการ', $2, $3, $4, $1, 'pending', 'normal')
            RETURNING id
            """,
            room_id,
            "ไฟในโรงยิมไม่ติด",
            "สว่างไม่พอ",
            reporter_id,
        )
        # เคลียร์ประกาศ seed (init_db วิ่งซ้ำตอน TestClient เปิด app → seed ใหม่) ให้เทส deterministic
        await conn.execute("DELETE FROM announcements WHERE deleted_at IS NULL")
        # ประกาศ 2 รายการ (urgent + normal) เพื่อตรวจลำดับ
        urg_id = await conn.fetchval(
            "INSERT INTO announcements (message, priority) VALUES ($1, 'urgent') RETURNING id",
            "ปิดห้องน้ำหญิงชั้น 2 ชั่วคราวเพื่อซ่อมแซม",
        )
        normal_id = await conn.fetchval(
            "INSERT INTO announcements (message, priority) VALUES ($1, 'normal') RETURNING id",
            "แจ้งเรื่องห้องเรียนได้ทุกเวลาผ่าน PIRIvoice",
        )

    return {
        "room_id": room_id,
        "reporter_id": reporter_id,
        "resolved_id": resolved_id,
        "urgent_announcement_id": urg_id,
        "normal_announcement_id": normal_id,
    }


@pytest.mark.asyncio
async def test_public_stats(client, db_pool, public_world):
    """GET /api/v1/public/stats — สถิติภาพรวมถูกต้อง + deep DB verify"""
    res = client.get("/api/v1/public/stats")
    assert res.status_code == 200
    data = res.json()

    assert data["total_issues"] == 2  # resolved 1 + pending 1
    assert data["resolved_rate_percent"] == 50.0
    assert data["avg_resolve_hours"] > 0
    assert isinstance(data["active_talk_threads"], int)
    assert isinstance(data["active_votes"], int)

    # Deep DB verify: นับจริงในฐานข้อมูลต้องตรงกับที่ API ตอบ
    async with db_pool.acquire() as conn:
        db_total = await conn.fetchval("SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL")
        assert db_total == data["total_issues"]


@pytest.mark.asyncio
async def test_public_resolved_cases(client, db_pool, public_world):
    """GET /api/v1/public/resolved-cases — เฉพาะเรื่อง resolved + mask ตัวตน"""
    res = client.get("/api/v1/public/resolved-cases", params={"limit": 5})
    assert res.status_code == 200
    data = res.json()

    assert isinstance(data, list)
    assert len(data) == 1  # pending ไม่โผล่
    case = data[0]
    assert case["id"] == str(public_world["resolved_id"])
    assert case["title"] == "แก้ไขห้องน้ำหญิงชั้น 2"
    assert case["category"] == "สิ่งแวดล้อม"
    assert case["reporter_mask"].startswith("นักเรียน ม.4")  # mask ตัวตนผู้แจ้ง
    assert case["solution_summary"] == "ซ่อมท่อและทำความสะอาดเรียบร้อยแล้ว"
    assert case["department_in_charge"] == "สภานักเรียน"  # council_member
    assert case["impact_score"] == 7  # priority=high → 7
    assert case["duration_hours"] is not None

    # Deep DB verify: resolved_at จริงใน DB ต้องไม่เป็น NULL
    async with db_pool.acquire() as conn:
        db_resolved_at = await conn.fetchval(
            "SELECT resolved_at FROM issues WHERE id = $1",
            public_world["resolved_id"],
        )
        assert db_resolved_at is not None


@pytest.mark.asyncio
async def test_public_resolved_cases_limit(client, db_pool, public_world):
    """limit ทำงาน (แม้มี 1 เรื่อง limit=0 ต้อง reject)"""
    res = client.get("/api/v1/public/resolved-cases", params={"limit": 0})
    assert res.status_code == 422  # ge=1


@pytest.mark.asyncio
async def test_public_announcements_order(client, public_world):
    """GET /api/v1/public/announcements — urgent มาก่อน normal"""
    res = client.get("/api/v1/public/announcements")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["priority"] == "urgent"
    assert data[1]["priority"] == "normal"
    assert data[0]["message"] == "ปิดห้องน้ำหญิงชั้น 2 ชั่วคราวเพื่อซ่อมแซม"
    assert data[1]["link"] is None
