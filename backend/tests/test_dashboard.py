# === Dashboard API Tests: 3 หมวดหลัก + scope ตามบทบาท ===
import random
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from services import auth_service


@pytest_asyncio.fixture
async def dashboard_world(db_pool):
    """สร้างโลกทดสอบ: ห้อง ม.4 + ม.5, นักเรียน, ครู ม.4, ครูสภา, แอดมิน"""
    room_4 = f"ม.4/{random.randint(100, 200)}"
    room_5 = f"ม.5/{random.randint(100, 200)}"
    async with db_pool.acquire() as conn:
        room4_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.4') RETURNING id",
            room_4, room_4
        )
        room5_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5') RETURNING id",
            room_5, room_5
        )

    def _sid(prefix):
        return f"{prefix}{random.randint(1000, 9999)}"

    users = {}
    # นักเรียน ม.4 / ม.5 + หัวหน้าห้อง ม.4 (ใช้เปลี่ยนสถานะเรื่อง)
    users["s4"] = await _register(db_pool, _sid("S4"), "1234", "เด็ก ม.4", _sid("S4"), room_4, "student")
    users["s5"] = await _register(db_pool, _sid("S5"), "1234", "เด็ก ม.5", _sid("S5"), room_5, "student")
    users["head"] = await _register(db_pool, _sid("HD"), "1234", "หัวหน้าห้อง ม.4", _sid("HD"), room_4, "class_president")
    # ครูทั่วไป → staff_level = ม.4
    users["teacher"] = await _register(db_pool, _sid("TC"), "1234", "ครู ม.4", _sid("TC"), room_4, "teacher")
    # ครูสภา / แอดมิน: school-wide (ไม่มีห้อง)
    users["teacher_council"] = await _register(db_pool, _sid("SC"), "1234", "ครูสภา", _sid("SC"), "", "teacher_council")
    users["admin"] = await _register(db_pool, _sid("AD"), "1234", "แอดมิน", _sid("AD"), "", "admin")

    users["room4_id"] = room4_id
    users["room5_id"] = room5_id
    users["room4_code"] = room_4
    users["room5_code"] = room_5
    return users


async def _register(db_pool, username, password, full_name, student_id, room_code, class_role):
    """สมัคร user (async) + สร้าง token — await ใน async fixture"""
    uid = await auth_service.register_user(
        db_pool, username, password, full_name, student_id, room_code, 1, class_role
    )
    return {
        "user_id": uid,
        "token": auth_service.create_access_token(uid),
    }


def _mk(client, world, *, main_category="suggestion", category="academic", title="เรื่อง",
        desc="รายละเอียด", room_key="room4_id", token=None, anonymous=False):
    """สร้างเรื่องด้วยนักเรียน ม.4 (default)"""
    who = token or world["s4"]["token"]
    return client.post("/api/issues", json={
        "main_category": main_category, "category": category, "title": title,
        "description": desc, "is_anonymous": anonymous,
        "room_id": world[room_key],
    }, headers={"Authorization": f"Bearer {who}"})


def _accept(client, world, issue_id, actor="head", days=2):
    return client.post(f"/api/issues/{issue_id}/accept", json={"estimated_days": days},
                       headers={"Authorization": f"Bearer {world[actor]['token']}"})


def _resolve(client, world, issue_id, actor="head"):
    return client.post(f"/api/issues/{issue_id}/resolve", json={"reason": "เรียบร้อย"},
                       headers={"Authorization": f"Bearer {world[actor]['token']}"})


def _escalate(client, world, issue_id, actor="head"):
    return client.post(f"/api/issues/{issue_id}/escalate", json={"reason": "เกินความสามารถ"},
                       headers={"Authorization": f"Bearer {world[actor]['token']}"})


def _cancel(client, world, issue_id, actor="s4"):
    return client.post(f"/api/issues/{issue_id}/cancel", json={"reason": "ส่งผิด"},
                       headers={"Authorization": f"Bearer {world[actor]['token']}"})


def _dashboard(client, world, who="admin"):
    return client.get("/api/dashboard/summary",
                      headers={"Authorization": f"Bearer {world[who]['token']}"})


# === Section 1: การควบคุมสิทธิ์ + scope ตามบทบาท ===
@pytest.mark.asyncio
async def test_dashboard_access_control(client, dashboard_world):
    """นักเรียนไม่มีสิทธิ์ดู dashboard (403) แต่ครู/ครูสภา/แอดมินดูได้"""
    world = dashboard_world

    # นักเรียน → 403
    res = _dashboard(client, world, "s4")
    assert res.status_code == 403

    # ครูทั่วไป → 200 + scope level (ม.4)
    res = _dashboard(client, world, "teacher")
    assert res.status_code == 200
    body = res.json()
    assert body["scope"] == "level"
    assert body["scope_label"] == "ม.4"

    # ครูสภา / แอดมิน → 200 + scope all
    for who in ("teacher_council", "admin"):
        res = _dashboard(client, world, who)
        assert res.status_code == 200, f"{who} → {res.status_code}: {res.text}"
        assert res.json()["scope"] == "all"
        assert res.json()["scope_label"] is None


@pytest.mark.asyncio
async def test_dashboard_teacher_level_scope(client, db_pool, dashboard_world):
    """
    ครู ม.4 เห็นสถิติเฉพาะเรื่อง/ห้อง/นักเรียนของระดับ ม.4 เท่านั้น
    ส่วนครูสภา/แอดมินเห็นทั้งระบบ — ตรวจลึกถึง DB ด้วย
    """
    world = dashboard_world

    # เรื่องใน ม.4 (2 เรื่อง) + ม.5 (1 เรื่อง)
    assert _mk(client, world, title="เรื่อง ม.4 เรื่องที่ 1").status_code == 200
    assert _mk(client, world, title="เรื่อง ม.4 เรื่องที่ 2").status_code == 200
    assert _mk(client, world, title="เรื่อง ม.5", room_key="room5_id",
               token=world["s5"]["token"]).status_code == 200

    # --- ครู ม.4: ต้องเห็นแค่เรื่อง ม.4 (2 เรื่อง) ---
    res = _dashboard(client, world, "teacher")
    assert res.status_code == 200
    body = res.json()
    assert body["total_issues"] == 2, f"ครู ม.4 ต้องเห็น 2 เรื่อง แต่ได้ {body['total_issues']}"
    assert sum(c["total"] for c in body["main_categories"]) == 2

    # Deep DB verify: นับเรื่องจริงเฉพาะ ม.4
    async with db_pool.acquire() as conn:
        db_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM issues i JOIN rooms r ON r.id = i.room_id
            WHERE i.deleted_at IS NULL AND r.level = 'ม.4'
            """
        )
    assert body["total_issues"] == db_count == 2

    # ครู ม.4 ต้องเห็นนักเรียน/ห้องเฉพาะระดับ ม.4
    async with db_pool.acquire() as conn:
        db_students_4 = await conn.fetchval(
            "SELECT COUNT(*) FROM students s JOIN rooms r ON r.id = s.room_id WHERE s.deleted_at IS NULL AND r.level = 'ม.4'"
        )
        db_rooms_4 = await conn.fetchval(
            "SELECT COUNT(*) FROM rooms r WHERE r.deleted_at IS NULL AND r.level = 'ม.4'"
        )
    assert body["total_students"] == db_students_4
    assert body["total_rooms"] == db_rooms_4 == 1

    # recent_issues (query แยกจากตัวนับ) ของครู ม.4 ต้องไม่มีเรื่อง ม.5 ปน
    teacher_recent_ids = {
        r["id"] for cat in body["main_categories"] for r in cat["recent_issues"]
    }
    async with db_pool.acquire() as conn:
        m5_issue_id = await conn.fetchval(
            """
            SELECT i.id FROM issues i JOIN rooms r ON r.id = i.room_id
            WHERE r.level = 'ม.5' AND i.deleted_at IS NULL LIMIT 1
            """
        )
    assert m5_issue_id is not None
    assert m5_issue_id not in teacher_recent_ids, "ครู ม.4 เห็นเรื่องของ ม.5 ในเรื่องล่าสุด — ข้อมูลรั่ว"

    # ครูระดับชั้นต้องไม่เห็นสถิติการเข้าระบบของทั้งโรงเรียน (ข้อมูลส่วนบุคคลข้ามระดับ)
    assert body["usage_count"] == 0
    assert body["recent_logins"] == []

    # --- แอดมิน: เห็นทั้ง 3 เรื่อง + ข้อมูลการเข้าระบบ (scope all) ---
    res = _dashboard(client, world, "admin")
    assert res.status_code == 200
    assert res.json()["total_issues"] == 3


@pytest.mark.asyncio
async def test_dashboard_teacher_without_level_scope(client, db_pool, dashboard_world):
    """
    ครูที่ยังไม่กำหนด staff_level → scope 'none' เห็นข้อมูลเป็น 0
    (เดิมตกเป็น 'pyramid' → dashboard แปลงเป็น 'all' = เห็นทั้งโรงเรียน — ข้อมูลรั่ว)
    """
    world = dashboard_world

    # ให้ระบบมีข้อมูล (1 เรื่องใน ม.4) — ครูไม่มีระดับชั้นต้องไม่เห็น
    assert _mk(client, world, title="เรื่องใน ม.4").status_code == 200

    # ครูที่สมัครโดยไม่ระบุห้อง → staff_level = NULL
    sid = f"TN{random.randint(1000, 9999)}"
    teacher_none = await _register(db_pool, sid, "1234", "ครูยังไม่ตั้งระดับ", sid, "", "teacher")

    res = client.get("/api/dashboard/summary",
                     headers={"Authorization": f"Bearer {teacher_none['token']}"})
    assert res.status_code == 200, f"→ {res.status_code}: {res.text}"
    body = res.json()
    assert body["scope"] == "none", f"ต้องเป็น none แต่ได้ {body['scope']}"
    assert body["scope_label"] is None
    assert body["total_issues"] == 0
    assert body["total_students"] == 0
    assert body["total_rooms"] == 0
    assert body["usage_count"] == 0
    assert body["recent_logins"] == []
    assert all(c["total"] == 0 for c in body["main_categories"])


@pytest.mark.asyncio
async def test_dashboard_council_member_scope_fail_closed(client, db_pool, dashboard_world):
    """
    council_member (สภานักเรียน) มี VIEW_DASHBOARD แต่อยู่นอก SCOPE_ALL_ROLES / SCOPE_LEVEL_ROLES
    → ต้อง fail-closed เป็น scope 'none' (ไม่เห็นตัวเลขทั้งโรงเรียน + ข้อมูลเข้าระบบ)
    (เดิม scope 'pyramid' รั่วไปเป็น 'all' — เห็น total_issues ทั้งโรงเรียน + recent_logins)
    """
    world = dashboard_world

    # ให้ระบบมีข้อมูล (1 เรื่องใน ม.4) — สภานักเรียนต้องไม่เห็น
    assert _mk(client, world, title="เรื่องใน ม.4").status_code == 200

    sid = f"CM{random.randint(1000, 9999)}"
    council_member = await _register(db_pool, sid, "1234", "สภานักเรียน", sid, "", "council_member")

    res = client.get("/api/dashboard/summary",
                     headers={"Authorization": f"Bearer {council_member['token']}"})
    assert res.status_code == 200, f"→ {res.status_code}: {res.text}"
    body = res.json()
    assert body["scope"] == "none", f"ต้อง fail-closed เป็น none แต่ได้ {body['scope']}"
    assert body["scope_label"] is None
    assert body["total_issues"] == 0
    assert body["total_students"] == 0
    assert body["total_rooms"] == 0
    assert body["usage_count"] == 0, "ห้ามเห็นข้อมูลการเข้าระบบ (ข้อมูลส่วนบุคคลข้ามระดับ)"
    assert body["recent_logins"] == []
    assert all(c["total"] == 0 for c in body["main_categories"])


@pytest.mark.asyncio
async def test_dashboard_trend_excludes_unknown_main_category(client, db_pool, dashboard_world):
    """
    เรื่องที่มี main_category อยู่นอก config (เก่า/insert ตรง) ต้องไม่ถูกนับใน trend
    — trend ต้องนับจาก key set เดียวกับ total_issues/by_status (บทเรียน: "Dashboard หลาย query รวมหมวดเดียว")
    มิฉะนั้นกราฟขึ้นเรื่องที่ตัวเลขอื่นไม่นับ → ตัวเลขในหน้าจอไม่ตรงกัน
    """
    world = dashboard_world

    # เรื่องปกติ 1 เรื่อง (ถูกนับทั้งใน total + trend)
    assert _mk(client, world, title="เรื่องปกติ").status_code == 200

    # insert ตรง: หมวดหลักเก่าที่ไม่อยู่ใน config (สร้างล่าสุด → อยู่ในช่วง 7 วัน)
    # (API กรองหมวดไม่อนุญาตให้สร้างด้วยหมวดนอก config — สถานการณ์จริงคือข้อมูลเดิม/insert ตรง)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO issues (room_id, main_category, category, title, description)
            VALUES ($1, 'legacy_main', 'legacy_cat', 'หมวดเก่า', 'ทดสอบ')
            """,
            world["room4_id"],
        )

    body = _dashboard(client, world, "admin").json()
    # ไม่ถูกนับใน total
    assert body["total_issues"] == 1, f"เรื่องหมวดเก่าต้องไม่ถูกนับ: {body['total_issues']}"
    # ไม่ถูกนับใน trend (7 วันต้องตรงกับ total — นับจาก key set เดียวกัน)
    assert sum(t["count"] for t in body["trend"]) == 1, f"trend ต้องไม่รวมหมวดเก่า: {body['trend']}"


# === Section 2: กลุ่มตาม 3 หมวดหลัก + สถานะ + หมวดย่อย + เรื่องล่าสุด ===
@pytest.mark.asyncio
async def test_dashboard_main_categories_grouping(client, db_pool, dashboard_world):
    """สถิติแบ่งตาม 3 หมวดหลัก ชัดเจน: total/by_status/top_subcategories/recent_issues"""
    world = dashboard_world

    # ---- สร้างเรื่องหลายหมวด + หลายสถานะ ----
    # suggestion: academic 2 (1 pending, 1 resolved) + discipline 1 (pending) = 3
    r = _mk(client, world, main_category="suggestion", category="academic", title="สอ.วิชาการ 1")
    i_acad1 = r.json()["id"]
    assert _accept(client, world, i_acad1).status_code == 200
    assert _resolve(client, world, i_acad1).status_code == 200
    assert _mk(client, world, main_category="suggestion", category="academic", title="สอ.วิชาการ 2").status_code == 200
    assert _mk(client, world, main_category="suggestion", category="discipline", title="สอ.วินัย").status_code == 200

    # wellbeing: mental_health 1 (escalated) = 1
    r = _mk(client, world, main_category="wellbeing", category="mental_health", title="สุขภาพใจ")
    i_well = r.json()["id"]
    assert _accept(client, world, i_well).status_code == 200
    assert _escalate(client, world, i_well).status_code == 200

    # report: complaint 2 (1 in_progress, 1 cancelled) + grievance 1 (pending) = 3
    r = _mk(client, world, main_category="report", category="complaint", title="ร้องทุกข์ 1")
    i_comp1 = r.json()["id"]
    assert _accept(client, world, i_comp1).status_code == 200
    r = _mk(client, world, main_category="report", category="complaint", title="ร้องทุกข์ 2")
    i_comp2 = r.json()["id"]
    assert _cancel(client, world, i_comp2).status_code == 200
    assert _mk(client, world, main_category="report", category="grievance", title="ร้องเรียน").status_code == 200

    # ---- เรียก dashboard (admin) ----
    res = _dashboard(client, world, "admin")
    assert res.status_code == 200
    body = res.json()
    assert body["total_issues"] == 7

    cats = {c["code"]: c for c in body["main_categories"]}
    assert set(cats.keys()) == {"suggestion", "wellbeing", "report"}

    # ---- suggestion: total 3, status pending 2 / resolved 1 ----
    sug = cats["suggestion"]
    assert sug["label"] == "เสนอความคิดเห็น"
    assert sug["total"] == 3
    sug_status = {s["status"]: s["count"] for s in sug["by_status"]}
    assert sug_status["pending"] == 2
    assert sug_status["resolved"] == 1
    assert sug_status["in_progress"] == 0  # เติม 0 ให้ครบ
    # หมวดย่อย: ครบ 5 หัวข้อ เรียง count มากไปน้อย (อันเยอะสุดอยู่บน) — หมวดที่ 0 เรื่องก็ยังโชว์
    assert [s["category"] for s in sug["subcategories"]] == \
        ["academic", "discipline", "reception", "activity", "democracy"]
    assert sug["subcategories"][0]["label"] == "วิชาการ"
    assert sug["subcategories"][0]["count"] == 2
    sug_subs = {s["category"]: s for s in sug["subcategories"]}
    # สถานะภายในหมวดย่อย (academic: 1 pending + 1 resolved)
    acad_status = {s["status"]: s["count"] for s in sug_subs["academic"]["by_status"]}
    assert acad_status["pending"] == 1
    assert acad_status["resolved"] == 1
    assert acad_status["in_progress"] == 0  # เติม 0 ให้ครบทุกสถานะ
    # หมวดที่ไม่มีเรื่อง → count 0 (แสดงครบทุกหัวข้อตาม config)
    assert sug_subs["reception"]["count"] == 0
    # sum(subcategories) == total (ตัวเลขจาก key set เดียวกัน)
    assert sum(s["count"] for s in sug["subcategories"]) == sug["total"] == 3
    # description ของหมวดหลัก + หมวดย่อย ต้องไม่ว่าง
    assert sug["description"]
    assert sug_subs["academic"]["description"]
    # งานเกินเวลาในหมวดนี้ = 0
    assert sug["overdue"] == 0
    # เรื่องล่าสุดต้องมีทั้ง 3 เรื่อง
    sug_ids = {r["id"] for r in sug["recent_issues"]}
    assert len(sug["recent_issues"]) == 3
    assert i_acad1 in sug_ids

    # ---- wellbeing: total 1, escalated 1 ----
    well = cats["wellbeing"]
    assert well["label"] == "สุขภาวะทางกายและใจ"
    assert well["total"] == 1
    well_status = {s["status"]: s["count"] for s in well["by_status"]}
    assert well_status["escalated"] == 1
    well_subs = {s["category"]: s for s in well["subcategories"]}
    # mental_health 1 เรื่อง → ขึ้นก่อน physical_health 0 เรื่อง
    assert [s["category"] for s in well["subcategories"]] == ["mental_health", "physical_health"]
    assert well_subs["mental_health"]["count"] == 1
    assert well_subs["physical_health"]["count"] == 0
    assert well["description"]
    assert [r["id"] for r in well["recent_issues"]] == [i_well]
    assert well["recent_issues"][0]["status"] == "escalated"

    # ---- report: total 3, in_progress 1 / pending 1 / cancelled 1 ----
    rep = cats["report"]
    assert rep["label"] == "แจ้งเหตุ"
    assert rep["total"] == 3
    rep_status = {s["status"]: s["count"] for s in rep["by_status"]}
    assert rep_status["in_progress"] == 1
    assert rep_status["pending"] == 1
    assert rep_status["cancelled"] == 1
    rep_subs = {s["category"]: s for s in rep["subcategories"]}
    assert [s["category"] for s in rep["subcategories"]] == ["complaint", "grievance"]
    assert rep["subcategories"][0]["label"] == "ร้องทุกข์"
    assert rep["subcategories"][0]["count"] == 2
    # สถานะภายในหมวดย่อย (complaint: 1 in_progress + 1 cancelled)
    comp_status = {s["status"]: s["count"] for s in rep_subs["complaint"]["by_status"]}
    assert comp_status["in_progress"] == 1
    assert comp_status["cancelled"] == 1
    assert sum(s["count"] for s in rep["subcategories"]) == rep["total"] == 3
    assert rep["overdue"] == 0

    # by_status รวมทั้งระบบ (เรียงตาม STATUS_ORDER เติม 0)
    all_status = {s["status"]: s["count"] for s in body["by_status"]}
    assert all_status["pending"] == 3     # สอ 2 + ร้องเรียน 1
    assert all_status["in_progress"] == 1
    assert all_status["escalated"] == 1
    assert all_status["resolved"] == 1
    assert all_status["cancelled"] == 1

    # ---- Deep DB verify: รวมจำนวนตาม DB ----
    async with db_pool.acquire() as conn:
        db_total = await conn.fetchval("SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL")
        db_by_cat = await conn.fetchval(
            "SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL AND main_category = 'suggestion'"
        )
        # deep verify per-status (ไม่ใช่แค่รวม) — กัน regression ที่รวมถูกแต่แยกผิด
        db_status_rows = await conn.fetch(
            "SELECT status, COUNT(*) AS cnt FROM issues WHERE deleted_at IS NULL GROUP BY status"
        )
    db_by_status = {r["status"]: r["cnt"] for r in db_status_rows}
    for st in ("pending", "in_progress", "escalated", "resolved", "cancelled", "rejected"):
        assert all_status[st] == db_by_status.get(st, 0), f"สถานะ {st}: body={all_status[st]} DB={db_by_status.get(st, 0)}"

    assert body["total_issues"] == db_total == 7
    assert sug["total"] == db_by_cat == 3

    # ---- trend: 7 วัน + รวมเรื่อง 7 (ใช้ sum — กัน flaky ตอนข้ามเที่ยงคืน Asia/Bangkok) ----
    assert len(body["trend"]) == 7
    assert sum(t["count"] for t in body["trend"]) == 7


# === Section 2.5: ยกเลิก/ปัดตก (cancelled = ผู้แจ้ง, rejected = ผู้ดูแล) ===
@pytest.mark.asyncio
async def test_cancel_by_manager_becomes_rejected(client, db_pool, dashboard_world):
    """
    ผู้แจ้งยกเลิก → 'cancelled' (ถูกยกเลิก)
    ผู้ดูแล (หัวหน้าห้องผู้รับ) ปัดตก → 'rejected' (ถูกปัดตก) + ไทม์ไลน์ note มีคำว่า "ถูกปัดตก"
    """
    world = dashboard_world

    # ผู้แจ้ง (s4) ยกเลิกเรื่องของตัวเอง → cancelled
    r = _mk(client, world, title="ผู้แจ้งยกเลิก")
    i_reporter = r.json()["id"]
    assert _cancel(client, world, i_reporter, actor="s4").status_code == 200
    body = client.get(
        f"/api/issues/{i_reporter}",
        headers={"Authorization": f"Bearer {world['s4']['token']}"},
    ).json()
    assert body["status"] == "cancelled"

    # ผู้ดูแล (หัวหน้าห้องผู้รับเรื่อง) ปัดตก → rejected
    r = _mk(client, world, title="ผู้ดูแลปัดตก")
    i_man = r.json()["id"]
    assert _accept(client, world, i_man, actor="head").status_code == 200
    assert _cancel(client, world, i_man, actor="head").status_code == 200
    body = client.get(
        f"/api/issues/{i_man}",
        headers={"Authorization": f"Bearer {world['s4']['token']}"},
    ).json()
    assert body["status"] == "rejected"
    rejected_hist = [h for h in body["status_history"] if h["status"] == "rejected"]
    assert rejected_hist and "ถูกปัดตก" in (rejected_hist[-1]["note"] or "")

    # Deep DB verify: status + note จริงในฐานข้อมูล
    async with db_pool.acquire() as conn:
        db_status = await conn.fetchval("SELECT status FROM issues WHERE id = $1", i_man)
        db_note = await conn.fetchval(
            "SELECT note FROM issue_status_history WHERE issue_id = $1 AND status = 'rejected' "
            "ORDER BY id DESC LIMIT 1",
            i_man,
        )
        db_reporter_status = await conn.fetchval("SELECT status FROM issues WHERE id = $1", i_reporter)
    assert db_status == "rejected"
    assert db_note and "ถูกปัดตก" in db_note
    assert db_reporter_status == "cancelled"

    # คนนอก (ไม่ใช่ผู้แจ้ง/ผู้รับ/admin) → ปัดตกไม่ได้ (403)
    r = _mk(client, world, title="คนนอกปัดตกไม่ได้")
    i_out = r.json()["id"]
    assert _cancel(client, world, i_out, actor="s5").status_code == 403


# === Section 3: งานเกินเวลา (overdue) ===
@pytest.mark.asyncio
async def test_dashboard_overdue_count(client, db_pool, dashboard_world):
    """เรื่อง in_progress ที่ countdown เลยกำหนด → นับเป็น overdue"""
    world = dashboard_world

    # เรื่อง A: รับ + ยังไม่เกิน (deadline อนาคต)
    r = _mk(client, world, main_category="report", category="complaint", title="ไม่เกิน")
    i_a = r.json()["id"]
    assert _accept(client, world, i_a, days=30).status_code == 200

    # เรื่อง B: รับ + แก้ deadline ย้อนหลังผ่าน DB → เกินเวลา
    r = _mk(client, world, main_category="report", category="complaint", title="เกินเวลา")
    i_b = r.json()["id"]
    assert _accept(client, world, i_b, days=30).status_code == 200
    async with db_pool.acquire() as conn:
        past = datetime.now(timezone.utc) - timedelta(days=1)
        await conn.execute(
            "UPDATE issue_countdowns SET deadline = $1 WHERE issue_id = $2",
            past, i_b
        )

    # เรื่อง C: มี 2 countdown — อันเก่าเกิน + อันใหม่ยังไม่เกิน (ยืดเวลา)
    # 🔍 พิสูจน์กฎ "นับเฉพาะ countdown ล่าสุด" — ถ้า implementation นับ countdown ไหนก็ได้ที่เกิน เรื่อง C จะโดนนับด้วย
    r = _mk(client, world, main_category="report", category="complaint", title="ยืดเวลาแล้ว")
    i_c = r.json()["id"]
    assert _accept(client, world, i_c, days=30).status_code == 200
    async with db_pool.acquire() as conn:
        past = datetime.now(timezone.utc) - timedelta(days=1)
        await conn.execute(
            "UPDATE issue_countdowns SET deadline = $1 WHERE issue_id = $2",
            past, i_c
        )
        future = datetime.now(timezone.utc) + timedelta(days=30)
        # แทรก countdown ใหม่ (deadline อนาคต) — จำลองการยืดเวลาของผู้รับเรื่อง
        await conn.execute(
            """
            INSERT INTO issue_countdowns (issue_id, assignee_id, estimated_days, deadline)
            SELECT $1, assignee_id, estimated_days, $2
            FROM issue_countdowns WHERE issue_id = $1
            ORDER BY id DESC LIMIT 1
            """,
            i_c, future
        )

    res = _dashboard(client, world, "admin")
    assert res.status_code == 200
    body = res.json()
    assert body["overdue"] == 1, (
        f"ต้องมีแค่ 1 เรื่องเกินเวลา (เรื่อง C ยืดเวลาแล้ว ไม่นับ) แต่ได้ {body['overdue']}"
    )

    # งานเกินเวลารายหมวด: เรื่องที่เกินคือ report (B) — suggestion/wellbeing ต้องเป็น 0
    cats = {c["code"]: c for c in body["main_categories"]}
    assert cats["report"]["overdue"] == 1
    assert cats["suggestion"]["overdue"] == 0
    assert cats["wellbeing"]["overdue"] == 0
    # sum(รายหมวด) == overdue รวม (ตัวเลขชุดเดียวกัน)
    assert sum(c["overdue"] for c in body["main_categories"]) == body["overdue"] == 1

    # Deep DB verify: นับ "countdown ล่าสุดของแต่ละเรื่องที่เกินกำหนด" — เขียนต่างจาก service query
    # (service ใช้ MAX(id) + EXISTS, ตรงนี้ใช้ correlated ORDER BY DESC LIMIT 1 — ตรวจอิสระ)
    async with db_pool.acquire() as conn:
        db_overdue = await conn.fetchval(
            """
            SELECT COUNT(*) FROM issues i
            WHERE i.deleted_at IS NULL AND i.status = 'in_progress'
              AND (SELECT cd.deadline FROM issue_countdowns cd
                   WHERE cd.issue_id = i.id
                   ORDER BY cd.id DESC LIMIT 1) < NOW()
            """
        )
    assert body["overdue"] == db_overdue == 1


# === Section 4: กรองเรื่องตามหมวดหลัก (ใช้กับปุ่ม "ดูทั้งหมด" จาก Dashboard) ===
@pytest.mark.asyncio
async def test_issues_list_main_category_filter(client, dashboard_world):
    """GET /api/issues?main_category=suggestion → ได้เฉพาะเรื่องหมวด suggestion"""
    world = dashboard_world

    assert _mk(client, world, main_category="suggestion", category="academic", title="ข้อเสนอ").status_code == 200
    assert _mk(client, world, main_category="report", category="complaint", title="แจ้งเหตุ").status_code == 200

    res = client.get("/api/issues?main_category=suggestion",
                     headers={"Authorization": f"Bearer {world['admin']['token']}"})
    assert res.status_code == 200
    issues = res.json()["items"]
    assert len(issues) == 1
    assert issues[0]["main_category"] == "suggestion"
    assert issues[0]["title"] == "ข้อเสนอ"

    # หมวดหลักไม่ถูกต้อง → 400
    res = client.get("/api/issues?main_category=not_real",
                     headers={"Authorization": f"Bearer {world['admin']['token']}"})
    assert res.status_code == 400


# === Section 5: กรองหลายสถานะด้วย "," (ฟิลเตอร์ "ยังไม่เสร็จ" ฝั่ง server) ===
@pytest.mark.asyncio
async def test_issues_list_multi_status_filter(client, dashboard_world):
    """GET /api/issues?status=pending,in_progress → ได้เฉพาะสถานะที่ระบุ (ไม่ใช้ตัดฝั่ง client)"""
    world = dashboard_world

    # A: pending (ยังไม่รับ) / B: accept → in_progress / C: accept + resolve → resolved
    r = _mk(client, world, main_category="suggestion", category="academic", title="ค้าง")
    i_a = r.json()["id"]
    r = _mk(client, world, main_category="suggestion", category="academic", title="กำลังทำ")
    i_b = r.json()["id"]
    assert _accept(client, world, i_b).status_code == 200
    r = _mk(client, world, main_category="suggestion", category="academic", title="เสร็จแล้ว")
    i_c = r.json()["id"]
    assert _accept(client, world, i_c).status_code == 200
    assert _resolve(client, world, i_c).status_code == 200

    token = world["admin"]["token"]
    res = client.get("/api/issues?status=pending,in_progress",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    issues = res.json()["items"]
    assert {i["status"] for i in issues} == {"pending", "in_progress"}
    ids = {i["id"] for i in issues}
    assert i_a in ids and i_b in ids and i_c not in ids


# === Section 6: หมวดย่อยที่ไม่อยู่ใน config → รวมเข้า "อื่นๆ" (ตัวเลขยังตรง) ===
@pytest.mark.asyncio
async def test_dashboard_subcategory_unknown_folded_into_other(client, db_pool, dashboard_world):
    """
    หมวดย่อยที่ไม่อยู่ใน config (เช่นหมวดเก่าหลัง migration / insert ตรง) → dashboard รวมเข้า "อื่นๆ"
    ทำให้ sum(subcategories[].count) == total เสมอ (ไม่ทิ้งข้อมูล ไม่ให้ตัวเลขเพี้ยน)
    """
    world = dashboard_world

    # สร้างเรื่องหมวดย่อยปกติ 1 เรื่อง แล้วแก้ category เป็นค่าที่ไม่อยู่ใน config ผ่าน DB ตรงๆ
    # (API บังคับให้ตรง config — เลยต้อง bypass ผ่าน SQL)
    r = _mk(client, world, main_category="suggestion", category="academic", title="วิชาการ")
    assert r.status_code == 200
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE issues SET category = 'old_legacy' WHERE id = $1", r.json()["id"])

    res = _dashboard(client, world, "admin")
    assert res.status_code == 200
    body = res.json()
    sug = next(c for c in body["main_categories"] if c["code"] == "suggestion")

    assert sug["total"] == 1
    assert sum(s["count"] for s in sug["subcategories"]) == sug["total"] == 1
    # เรื่องที่ category ไม่อยู่ใน config → ไปอยู่ "อื่นๆ" ท้ายสุด
    assert sug["subcategories"][-1]["category"] == "_other"
    assert sug["subcategories"][-1]["label"] == "อื่นๆ"
    assert sug["subcategories"][-1]["count"] == 1
    # หมวดย่อยปกติใน config ยังเป็น 0
    normal = [s for s in sug["subcategories"] if s["category"] != "_other"]
    assert all(s["count"] == 0 for s in normal)


# === Section 7: กรองหมวดย่อย (ใช้กับลิงก์จาก Dashboard → หน้าเรื่องที่รับ) ===
@pytest.mark.asyncio
async def test_issues_list_subcategory_filter(client, dashboard_world):
    """GET /api/issues?main_category=suggestion&category=academic → เฉพาะเรื่องหมวดย่อยนั้น"""
    world = dashboard_world

    assert _mk(client, world, main_category="suggestion", category="academic", title="วิชาการ").status_code == 200
    assert _mk(client, world, main_category="suggestion", category="discipline", title="วินัย").status_code == 200
    assert _mk(client, world, main_category="report", category="complaint", title="ร้องทุกข์").status_code == 200

    token = world["admin"]["token"]
    # กรองหมวดหลัก + หมวดย่อย
    res = client.get("/api/issues?main_category=suggestion&category=academic",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    issues = res.json()["items"]
    assert len(issues) == 1
    assert issues[0]["category"] == "academic"
    assert issues[0]["main_category"] == "suggestion"
    assert issues[0]["title"] == "วิชาการ"

    # กรองแค่หมวดย่อย โดยไม่มีหมวดหลัก
    res = client.get("/api/issues?category=complaint",
                     headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    issues = res.json()["items"]
    assert len(issues) == 1
    assert issues[0]["category"] == "complaint"
