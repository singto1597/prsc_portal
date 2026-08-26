# === Issue Flow + Escalation Pyramid Tests ===
import json
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


def _create_issue(client, users, *, main_category="report", category="complaint", title="เรื่องทดสอบ",
                  desc="รายละเอียด", anonymous=False, room_id=None, token=None):
    return client.post("/api/issues", json={
        "main_category": main_category, "category": category, "title": title,
        "description": desc, "is_anonymous": anonymous,
        "room_id": room_id or users["student"]["room_id"],
    }, headers={"Authorization": f"Bearer {token or users['student']['token']}"})


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
    res = _create_issue(client, users, main_category="report", category="complaint",
                        title="ห้องน้ำพัง", desc="ห้องน้ำชั้น 2 พัง", anonymous=True)
    assert res.status_code == 200
    issue_id = res.json()["id"]

    # นักเรียนเห็นเรื่องตัวเอง (แม้ anonymous — ติดตามสถานะ)
    res = client.get(f"/api/issues/{issue_id}", headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 200

    # Council เห็นทุกเรื่อง (พีระมิด)
    res = client.get("/api/issues", headers={"Authorization": f"Bearer {council['token']}"})
    assert res.status_code == 200
    assert any(i["id"] == issue_id for i in res.json()["items"])

    # นักเรียน (คนอื่น) ไม่เห็นเรื่องของคนอื่น
    res = client.get("/api/issues", headers={"Authorization": f"Bearer {student['token']}"})
    assert all(i["reporter_id"] == student["user_id"] for i in res.json()["items"])


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


# === Section 4: หมวดหมู่ใหม่ (main_category + category) ===
@pytest.mark.asyncio
async def test_category_validation(client, issue_world):
    """หมวดหลัก/หมวดย่อยต้องตรงกับ config/categories.json"""
    users = issue_world

    # หมวดหลักไม่มีในระบบ → 422
    res = _create_issue(client, users, main_category="invalid_cat", category="complaint")
    assert res.status_code == 422

    # หมวดย่อยไม่ตรงกับหมวดหลัก (complaint ไม่ใช่หมวดย่อยของ suggestion) → 422
    res = _create_issue(client, users, main_category="suggestion", category="complaint")
    assert res.status_code == 422

    # หมวดย่อยถูกต้อง → 200
    for main_cat, cat in [
        ("suggestion", "academic"),
        ("suggestion", "discipline"),
        ("wellbeing", "mental_health"),
        ("wellbeing", "physical_health"),
        ("report", "complaint"),
        ("report", "grievance"),
    ]:
        res = _create_issue(client, users, main_category=main_cat, category=cat)
        assert res.status_code == 200, f"{main_cat}/{cat} → {res.status_code}: {res.text}"
        assert res.json()["main_category"] == main_cat
        assert res.json()["category"] == cat


# === Section 5: ครูทั่วไป (teacher) scope เฉพาะระดับชั้น + ครูสภา/แอดมิน เห็นทุกอย่าง ===
@pytest.mark.asyncio
async def test_teacher_scope_and_staff_full_access(client, db_pool):
    """ครู ม.4 เห็น/จัดการได้เฉพาะเรื่องระดับ ม.4 แต่ ครูสภา/แอดมิน เห็นทุกเรื่อง"""
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

    sid4 = _sid("S4")
    sid5 = _sid("S5")
    tid = _sid("TC")
    tcid = _sid("SC")
    adid = _sid("AD")

    uid4 = await auth_service.register_user(db_pool, sid4, "1234", "เด็ก ม.4", sid4, room_4, 1, "student")
    uid5 = await auth_service.register_user(db_pool, sid5, "1234", "เด็ก ม.5", sid5, room_5, 1, "student")
    # ครูทั่วไปสมัครในห้อง ม.4 → staff_level = ม.4
    teacher_uid = await auth_service.register_user(db_pool, tid, "1234", "ครู ม.4", tid, room_4, 1, "teacher")
    # ครูสภา / แอดมิน: school-wide (ไม่ผูกห้อง)
    tc_uid = await auth_service.register_user(db_pool, tcid, "1234", "ครูสภา", tcid, "", 0, "teacher_council")
    admin_uid = await auth_service.register_user(db_pool, adid, "1234", "แอดมิน", adid, "", 0, "admin")

    def _tok(uid):
        return auth_service.create_access_token(uid)

    users = {
        "s4": {"user_id": uid4, "token": _tok(uid4), "room_id": room4_id},
        "s5": {"user_id": uid5, "token": _tok(uid5), "room_id": room5_id},
        "teacher": {"user_id": teacher_uid, "token": _tok(teacher_uid)},
        "teacher_council": {"user_id": tc_uid, "token": _tok(tc_uid)},
        "admin": {"user_id": admin_uid, "token": _tok(admin_uid)},
    }

    # เรื่องใน ม.4 และ ม.5
    res = _create_issue(client, users, title="เรื่อง ม.4", room_id=room4_id, token=users["s4"]["token"])
    assert res.status_code == 200
    issue_4 = res.json()["id"]
    res = _create_issue(client, users, title="เรื่อง ม.5", room_id=room5_id, token=users["s5"]["token"])
    assert res.status_code == 200
    issue_5 = res.json()["id"]

    # --- ครู ม.4 ---
    # เห็นเรื่อง ม.4
    res = client.get(f"/api/issues/{issue_4}", headers={"Authorization": f"Bearer {users['teacher']['token']}"})
    assert res.status_code == 200
    # ไม่เห็นเรื่อง ม.5
    res = client.get(f"/api/issues/{issue_5}", headers={"Authorization": f"Bearer {users['teacher']['token']}"})
    assert res.status_code == 403
    # list เห็นเฉพาะเรื่อง ม.4
    res = client.get("/api/issues", headers={"Authorization": f"Bearer {users['teacher']['token']}"})
    assert res.status_code == 200
    ids = [i["id"] for i in res.json()["items"]]
    assert issue_4 in ids and issue_5 not in ids
    # รับเรื่อง ม.4 ได้ แต่รับเรื่อง ม.5 ไม่ได้
    res = client.post(f"/api/issues/{issue_4}/accept", json={"estimated_days": 2},
                      headers={"Authorization": f"Bearer {users['teacher']['token']}"})
    assert res.status_code == 200
    res = client.post(f"/api/issues/{issue_5}/accept", json={"estimated_days": 2},
                      headers={"Authorization": f"Bearer {users['teacher']['token']}"})
    assert res.status_code == 403

    # --- ครูสภา / แอดมิน: เห็นทุกเรื่อง + รับได้ (มี is_admin) ---
    for who in ("teacher_council", "admin"):
        tok = users[who]["token"]
        for iid in (issue_4, issue_5):
            res = client.get(f"/api/issues/{iid}", headers={"Authorization": f"Bearer {tok}"})
            assert res.status_code == 200, f"{who} ดูเรื่อง {iid} → {res.status_code}"
        res = client.get("/api/issues", headers={"Authorization": f"Bearer {tok}"})
        ids = [i["id"] for i in res.json()["items"]]
        assert issue_4 in ids and issue_5 in ids, f"{who} ต้องเห็นทั้ง 2 เรื่อง"


# === Section 6: แก้ไขเรื่อง (ผู้แจ้ง/admin) ===
@pytest.mark.asyncio
async def test_reporter_can_edit_issue(client, issue_world, db_pool):
    users = issue_world
    student = users["student"]

    res = _create_issue(client, users, title="เดิม", desc="รายละเอียดเดิม")
    assert res.status_code == 200
    issue_id = res.json()["id"]

    # แก้ title + description + category (เดิม main_category=report, category=complaint → grievance ใช้ได้)
    res = client.patch(f"/api/issues/{issue_id}",
                       json={"title": "แก้ไขแล้ว", "description": "รายละเอียดใหม่", "category": "grievance"},
                       headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 200, res.text
    assert res.json()["title"] == "แก้ไขแล้ว"
    assert res.json()["category"] == "grievance"

    # deep-DB verify
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT title, description, category, updated_at FROM issues WHERE id = $1", issue_id)
        assert row["title"] == "แก้ไขแล้ว"
        assert row["description"] == "รายละเอียดใหม่"
        assert row["category"] == "grievance"
        assert row["updated_at"] is not None
        # status_history มี note บอกว่าโดนแก้
        note = await conn.fetchval(
            "SELECT note FROM issue_status_history WHERE issue_id = $1 ORDER BY id DESC LIMIT 1",
            issue_id)
        assert note == "ผู้แจ้งแก้ไขข้อมูลเรื่อง"
        # audit log บันทึก old/new values (asyncpg คืน jsonb เป็น string → json.loads)
        audit = await conn.fetchrow(
            "SELECT old_values, new_values FROM audit_logs WHERE action = 'UPDATE_ISSUE' AND entity_id = $1",
            str(issue_id))
        assert audit is not None
        assert json.loads(audit["old_values"])["title"] == "เดิม"
        assert json.loads(audit["new_values"])["title"] == "แก้ไขแล้ว"


@pytest.mark.asyncio
async def test_non_reporter_cannot_edit(client, issue_world, db_pool):
    users = issue_world
    student, head = users["student"], users["head"]

    res = _create_issue(client, users, title="เดิม", desc="aaa")
    issue_id = res.json()["id"]

    # หัวหน้าห้อง (ไม่ใช่ผู้แจ้ง) พยายามแก้ → 403
    res = client.patch(f"/api/issues/{issue_id}", json={"title": "แฮก"},
                       headers={"Authorization": f"Bearer {head['token']}"})
    assert res.status_code == 403

    async with db_pool.acquire() as conn:
        title = await conn.fetchval("SELECT title FROM issues WHERE id = $1", issue_id)
        assert title == "เดิม"


@pytest.mark.asyncio
async def test_admin_can_edit(client, issue_world):
    users = issue_world
    council = users["council"]

    res = _create_issue(client, users, title="เรื่อง student", desc="aaa")
    issue_id = res.json()["id"]

    # admin (council_president is_admin=True) แก้เรื่องของคนอื่นได้
    res = client.patch(f"/api/issues/{issue_id}", json={"title": "admin แก้"},
                       headers={"Authorization": f"Bearer {council['token']}"})
    assert res.status_code == 200, res.text
    assert res.json()["title"] == "admin แก้"


@pytest.mark.parametrize("terminal_setup", ["resolved", "cancelled", "rejected"])
@pytest.mark.asyncio
async def test_edit_blocked_on_terminal_status(client, issue_world, db_pool, terminal_setup):
    users = issue_world
    student, head = users["student"], users["head"]

    res = _create_issue(client, users, title="เดิม", desc="aaa")
    issue_id = res.json()["id"]

    # ทำสถานะให้ปิดก่อน
    if terminal_setup == "resolved":
        client.post(f"/api/issues/{issue_id}/accept", json={"estimated_days": 2},
                    headers={"Authorization": f"Bearer {head['token']}"})
        client.post(f"/api/issues/{issue_id}/resolve", json={"reason": "เสร็จ"},
                    headers={"Authorization": f"Bearer {head['token']}"})
    elif terminal_setup == "cancelled":
        client.post(f"/api/issues/{issue_id}/cancel", json={"reason": "เลิกเอง"},
                    headers={"Authorization": f"Bearer {student['token']}"})
    elif terminal_setup == "rejected":
        client.post(f"/api/issues/{issue_id}/accept", json={"estimated_days": 2},
                    headers={"Authorization": f"Bearer {head['token']}"})
        client.post(f"/api/issues/{issue_id}/cancel", json={"reason": "ปัดตก"},
                    headers={"Authorization": f"Bearer {head['token']}"})

    # ผู้แจ้งพยายามแก้ → 400 (สถานะปิด)
    res = client.patch(f"/api/issues/{issue_id}", json={"title": "พยายามแก้"},
                       headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 400
    assert "ปิดแล้ว" in res.json()["detail"]

    async with db_pool.acquire() as conn:
        title = await conn.fetchval("SELECT title FROM issues WHERE id = $1", issue_id)
        assert title == "เดิม"


@pytest.mark.asyncio
async def test_edit_category_validation(client, issue_world):
    users = issue_world
    student = users["student"]

    res = _create_issue(client, users, main_category="report", category="complaint", title="หมวด", desc="aaa")
    assert res.status_code == 200
    issue_id = res.json()["id"]

    # เปลี่ยน main_category เฉยๆ → category เดิม (complaint) ไม่อยู่ใต้ suggestion → 400
    res = client.patch(f"/api/issues/{issue_id}", json={"main_category": "suggestion"},
                       headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 400

    # เปลี่ยนคู่ให้ถูกต้อง → 200
    res = client.patch(f"/api/issues/{issue_id}",
                       json={"main_category": "suggestion", "category": "academic"},
                       headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 200
    assert res.json()["main_category"] == "suggestion"
    assert res.json()["category"] == "academic"

    # เปลี่ยนเฉพาะ category ไม่ตรง main_category ปัจจุบัน (suggestion) → 400
    res = client.patch(f"/api/issues/{issue_id}", json={"category": "complaint"},
                       headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 400

    # main_category ไม่มีในระบบ → 422 (model validator)
    res = client.patch(f"/api/issues/{issue_id}", json={"main_category": "invalid_cat"},
                       headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_anonymous_toggle_resnapshots_name(client, issue_world, db_pool):
    users = issue_world
    student = users["student"]

    res = _create_issue(client, users, title="นิรนาม", desc="ไม่ระบุชื่อ", anonymous=True)
    assert res.status_code == 200
    issue_id = res.json()["id"]

    async with db_pool.acquire() as conn:
        assert await conn.fetchval("SELECT reporter_name FROM issues WHERE id = $1", issue_id) is None

    # ผู้แจ้งเปิดเผยชื่อ → backend re-snapshot ชื่อจริงให้
    res = client.patch(f"/api/issues/{issue_id}", json={"is_anonymous": False},
                       headers={"Authorization": f"Bearer {student['token']}"})
    assert res.status_code == 200, res.text
    assert res.json()["reporter_name"] is not None

    async with db_pool.acquire() as conn:
        name = await conn.fetchval("SELECT reporter_name FROM issues WHERE id = $1", issue_id)
        assert name is not None and name != ""
