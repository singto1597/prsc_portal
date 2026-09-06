# === Grade-scope ของหัวหน้าระดับ/ผู้ช่วย + exact-level (received=true) + filter หลายหมวด ===
# Requirement: "หัวหน้าระดับ" (level_president) เห็นได้เฉพาะเรื่องในระดับชั้นตัวเอง — ไม่รั่วข้ามชั้น
# Role ใหม่ level_vice_president (ผู้ช่วยหัวหน้าระดับ) มีสิทธิ์เท่า level_president
# received=true = EXACT LEVEL MATCH (เรื่องที่อยู่ระดับตัวเองพอดี — ไม่ดึงเรื่องระดับล่างติดมา)
import random

import pytest
import pytest_asyncio

from services import auth_service


@pytest_asyncio.fixture
async def grade_world(db_pool):
    """ห้อง 2 ระดับชั้น (ม.4 / ม.5) พร้อมผู้ใช้งานตามระดับ:
    - ม.4: ประธานระดับ (m4_level), ผู้ช่วยหัวหน้าระดับ (m4_vice), นักเรียน (m4_student)
    - ม.5: ประธานระดับ (m5_level), นักเรียน (m5_student)
    - admin: council_president (is_admin — เห็นทั้งโรงเรียน)
    - council member หนึ่งคน (ม.4) สำหรับเช็ค role hierarchy
    """
    rooms = {}
    for level_lbl in ("ม.4", "ม.5"):
        code = f"ร{random.randint(100, 999)}/{level_lbl[-1]}"
        async with db_pool.acquire() as conn:
            rid = await conn.fetchval(
                "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,$3) RETURNING id",
                code, code, level_lbl
            )
        rooms[level_lbl] = {"room_id": rid, "room_code": code}

    users = {}
    for label, role, level_lbl, no in [
        ("m4_student", "student", "ม.4", 1),
        ("m4_level", "level_president", "ม.4", 2),
        ("m4_vice", "level_vice_president", "ม.4", 3),
        ("m5_student", "student", "ม.5", 1),
        ("m5_level", "level_president", "ม.5", 2),
        ("council_member", "council_member", "ม.4", 4),
    ]:
        sid = f"G{random.randint(1000, 9999)}{label[:2].upper()}"
        uid = await auth_service.register_user(
            db_pool, sid, "1234", f"{label} ทดสอบ", sid,
            rooms[level_lbl]["room_code"], no, role
        )
        users[label] = {"user_id": uid, "token": auth_service.create_access_token(uid)}

    sid = f"G{random.randint(1000, 9999)}AD"
    uid = await auth_service.register_user(
        db_pool, sid, "1234", "แอดมิน ทดสอบ", sid, rooms["ม.4"]["room_code"], 9,
        "council_president"
    )
    users["admin"] = {"user_id": uid, "token": auth_service.create_access_token(uid)}

    users["rooms"] = rooms
    return users


def _post_issue(client, token, room_id, *, main_category="report", category="complaint",
                title="เรื่องทดสอบ", start="room"):
    res = client.post("/api/issues", json={
        "main_category": main_category, "category": category, "title": title,
        "description": "รายละเอียด", "is_anonymous": False,
        "room_id": room_id, "start_level": start,
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    return res.json()["id"]


async def _promote_level(db_pool, issue_id, level):
    """จำลองการ escalate: ตั้ง current_level ตรง ๆ (หัวเรื่องอยู่ระดับนั้นแล้ว)"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE issues SET current_level = $1, status = 'escalated' WHERE id = $2",
            level, issue_id
        )


def _get(client, token, issue_id):
    return client.get(f"/api/issues/{issue_id}",
                      headers={"Authorization": f"Bearer {token}"})


def _list(client, token, **params):
    return client.get("/api/issues", params=params,
                      headers={"Authorization": f"Bearer {token}"})


def _accept(client, token, issue_id, days=2):
    return client.post(f"/api/issues/{issue_id}/accept", json={"estimated_days": days},
                       headers={"Authorization": f"Bearer {token}"})


# ============================================================
# 1) หัวหน้าระดับ (level_president) เห็นเรื่องของตัวเองชั้นเท่านั้น
# ============================================================
@pytest.mark.asyncio
async def test_level_president_sees_own_grade_room_and_level(client, grade_world, db_pool):
    """ประธานระดับ ม.4 เห็นเรื่อง room + level ของ ม.4 (list + get)"""
    w = grade_world
    m4 = w["rooms"]["ม.4"]["room_id"]

    # เรื่อง room (นักเรียน ม.4 แจ้ง) + เรื่อง level (escalate ขึ้นมา)
    r_issue = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องห้อง ม.4")
    l_issue = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องระดับ ม.4")
    await _promote_level(db_pool, l_issue, "level")

    body = _list(client, w["m4_level"]["token"]).json()
    titles = {i["title"] for i in body["items"]}
    assert "เรื่องห้อง ม.4" in titles
    assert "เรื่องระดับ ม.4" in titles

    # GET รายละเอียดทั้ง 2 ได้ (ไม่ 403)
    assert _get(client, w["m4_level"]["token"], r_issue).status_code == 200
    assert _get(client, w["m4_level"]["token"], l_issue).status_code == 200


@pytest.mark.asyncio
async def test_level_president_cannot_see_other_grade(client, grade_world, db_pool):
    """ประธานระดับ ม.4 ต้องไม่เห็นเรื่องของ ม.5 (list ไม่มี / get → 403 / accept → 403)"""
    w = grade_world
    m5 = w["rooms"]["ม.5"]["room_id"]

    m5_issue = _post_issue(client, w["m5_student"]["token"], m5, title="เรื่องห้อง ม.5")

    # list: ไม่เจอเรื่อง ม.5
    body = _list(client, w["m4_level"]["token"]).json()
    assert all(i["id"] != m5_issue for i in body["items"])

    # get → 403
    assert _get(client, w["m4_level"]["token"], m5_issue).status_code == 403

    # accept → 403 (เรื่องคนละชั้น)
    assert _accept(client, w["m4_level"]["token"], m5_issue).status_code == 403


@pytest.mark.asyncio
async def test_level_vice_president_same_power_as_level_president(client, grade_world, db_pool):
    """ผู้ช่วยหัวหน้าระดับ (level_vice_president) มีสิทธิ์เท่า ประธานระดับ"""
    w = grade_world
    m4 = w["rooms"]["ม.4"]["room_id"]

    # เรื่องระดับ ม.4 ที่ยังไม่มีคนรับ
    l_issue = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องระดับ ม.4")
    await _promote_level(db_pool, l_issue, "level")

    # list เห็น + รับได้
    body = _list(client, w["m4_vice"]["token"]).json()
    assert any(i["id"] == l_issue for i in body["items"])
    assert _accept(client, w["m4_vice"]["token"], l_issue).status_code == 200

    # แต่รับเรื่อง ม.5 ไม่ได้
    m5 = w["rooms"]["ม.5"]["room_id"]
    m5_issue = _post_issue(client, w["m5_student"]["token"], m5, title="เรื่องห้อง ม.5")
    assert _accept(client, w["m4_vice"]["token"], m5_issue).status_code == 403


# ============================================================
# 2) received=true → EXACT LEVEL MATCH
# ============================================================
@pytest.mark.asyncio
async def test_received_level_role_exact_level(client, grade_world, db_pool):
    """received=true ของประธานระดับ ม.4 → เห็นเฉพาะเรื่อง current_level='level' ในชั้น ม.4
    (ไม่เห็นเรื่อง room ในห้องตัวเอง — เป็นคนละระดับ; ไม่เห็นเรื่อง ม.5)"""
    w = grade_world
    m4 = w["rooms"]["ม.4"]["room_id"]
    m5 = w["rooms"]["ม.5"]["room_id"]

    room_issue = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องห้อง ม.4")
    lvl_issue = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องระดับ ม.4")
    await _promote_level(db_pool, lvl_issue, "level")
    m5_issue = _post_issue(client, w["m5_student"]["token"], m5, title="เรื่องห้อง ม.5")

    body = _list(client, w["m4_level"]["token"], received="true").json()
    ids = {i["id"] for i in body["items"]}
    assert lvl_issue in ids            # เรื่องระดับ ม.4 (ของฉันชั้น) → เห็น
    assert room_issue not in ids       # เรื่องระดับห้อง ม.4 → ไม่เห็น (exact level)
    assert m5_issue not in ids         # เรื่อง ม.5 → ไม่เห็น (คนละชั้น)


@pytest.mark.asyncio
async def test_received_council_exact_level(client, grade_world, db_pool):
    """received=true ของสภา (council_president) → เห็นเฉพาะเรื่องระดับ council ไม่เห็น room/level"""
    w = grade_world
    m4 = w["rooms"]["ม.4"]["room_id"]

    room_issue = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องห้อง ม.4")
    council_issue = _post_issue(
        client, w["admin"]["token"], m4, title="เรื่องสภา ม.4", start="council"
    )
    # เรื่อง room ใน ม.5 ก็ไม่ควรติดมาด้วย
    m5 = w["rooms"]["ม.5"]["room_id"]
    _post_issue(client, w["m5_student"]["token"], m5, title="เรื่องห้อง ม.5")

    body = _list(client, w["admin"]["token"], received="true").json()
    ids = {i["id"] for i in body["items"]}
    assert council_issue in ids
    assert room_issue not in ids

    # นักเรียนไม่มี "เรื่องที่รับ" → ว่าง
    assert _list(client, w["m4_student"]["token"], received="true").json()["items"] == []


# ============================================================
# 3) Filter หลายหมวด (comma-separated) — ใช้กับหน้าเรื่องที่รับ ระดับฉัน
# ============================================================
@pytest.mark.asyncio
async def test_received_category_multi_filter(client, grade_world):
    """received=true + category='academic,discipline' → เฉพาะเรื่อง 2 หมวดนั้น (ระดับสภา)"""
    w = grade_world
    m4 = w["rooms"]["ม.4"]["room_id"]

    a_id = _post_issue(client, w["admin"]["token"], m4,
                       main_category="suggestion", category="academic",
                       title="หมวดวิชาการ", start="council")
    d_id = _post_issue(client, w["admin"]["token"], m4,
                       main_category="suggestion", category="discipline",
                       title="หมวดวินัย", start="council")
    act_id = _post_issue(client, w["admin"]["token"], m4,
                         main_category="suggestion", category="activity",
                         title="หมวดกิจกรรม", start="council")

    body = _list(client, w["admin"]["token"], received="true",
                 category="academic,discipline").json()
    ids = {i["id"] for i in body["items"]}
    assert a_id in ids and d_id in ids
    assert act_id not in ids


@pytest.mark.asyncio
async def test_issue_category_multi_filter_normal_list(client, grade_world):
    """list ปกติ (ไม่ต้อง received) ก็กรองหลายหมวดได้"""
    w = grade_world
    m4 = w["rooms"]["ม.4"]["room_id"]

    a_id = _post_issue(client, w["m4_student"]["token"], m4,
                       main_category="suggestion", category="academic", title="วิชาการ")
    d_id = _post_issue(client, w["m4_student"]["token"], m4,
                       main_category="suggestion", category="discipline", title="วินัย")

    body = _list(client, w["m4_student"]["token"], category="academic,discipline").json()
    ids = {i["id"] for i in body["items"]}
    assert a_id in ids and d_id in ids


# ============================================================
# 4) received=true + levels (มองลงตามพีระมิด — ระดับที่สูงกว่าดูระดับล่างได้)
# ============================================================
@pytest.mark.asyncio
async def test_received_council_levels_multi(client, grade_world, db_pool):
    """สภา (admin/council_president) received + levels=room,level,council →
    เห็นระดับล่างทั้งห้อง ม.4 + ม.5 (scope ทั้งโรงเรียน); default (ไม่ส่ง levels) ยังเป็น council เท่านั้น"""
    w = grade_world
    m4 = w["rooms"]["ม.4"]["room_id"]
    m5 = w["rooms"]["ม.5"]["room_id"]

    room_m4 = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องห้อง ม.4")
    room_m5 = _post_issue(client, w["m5_student"]["token"], m5, title="เรื่องห้อง ม.5")
    lvl_m4 = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องระดับ ม.4")
    await _promote_level(db_pool, lvl_m4, "level")
    council_issue = _post_issue(client, w["admin"]["token"], m4, title="เรื่องสภา", start="council")

    # default: ไม่ส่ง levels → เห็นเฉพาะระดับ council พอดี
    default_ids = {i["id"] for i in _list(client, w["admin"]["token"], received="true").json()["items"]}
    assert council_issue in default_ids
    assert room_m4 not in default_ids and room_m5 not in default_ids and lvl_m4 not in default_ids

    # มองลงทุกระดับ (ทั้ง ม.4 + ม.5 — council scope ทั้งโรงเรียน)
    body = _list(client, w["admin"]["token"], received="true", levels="room,level,council").json()
    ids = {i["id"] for i in body["items"]}
    assert council_issue in ids
    assert room_m4 in ids and room_m5 in ids      # เห็นระดับห้องทั้ง 2 ชั้น
    assert lvl_m4 in ids                          # เห็นระดับ level ด้วย

    # เลือกเฉพาะ room → เห็นแต่ระดับห้อง (ทั้ง 2 ชั้น) ไม่เห็น level/council
    body = _list(client, w["admin"]["token"], received="true", levels="room").json()
    ids = {i["id"] for i in body["items"]}
    assert room_m4 in ids and room_m5 in ids
    assert lvl_m4 not in ids and council_issue not in ids


@pytest.mark.asyncio
async def test_received_level_president_levels_down(client, grade_world, db_pool):
    """ประธานระดับ ม.4 received + levels=room,level → เห็นระดับ room+level เฉพาะชั้น ม.4
    (grade scope ยังบังคับ — ไม่เห็น ม.5; ไม่เห็น council ทั้งที่ขอมา)"""
    w = grade_world
    m4 = w["rooms"]["ม.4"]["room_id"]
    m5 = w["rooms"]["ม.5"]["room_id"]

    room_m4 = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องห้อง ม.4")
    room_m5 = _post_issue(client, w["m5_student"]["token"], m5, title="เรื่องห้อง ม.5")
    lvl_m4 = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องระดับ ม.4")
    await _promote_level(db_pool, lvl_m4, "level")
    lvl_m5 = _post_issue(client, w["m5_student"]["token"], m5, title="เรื่องระดับ ม.5")
    await _promote_level(db_pool, lvl_m5, "level")
    council_issue = _post_issue(client, w["admin"]["token"], m4, title="เรื่องสภา ม.4", start="council")

    body = _list(client, w["m4_level"]["token"], received="true", levels="room,level,council").json()
    ids = {i["id"] for i in body["items"]}
    assert room_m4 in ids and lvl_m4 in ids       # เห็น room+level ในชั้นตัวเอง
    assert room_m5 not in ids and lvl_m5 not in ids  # ไม่รั่วข้ามชั้น
    assert council_issue not in ids               # ขอ council มาแต่ band ไม่มี → ถูกตัด


@pytest.mark.asyncio
async def test_received_cannot_request_above_band(client, grade_world, db_pool):
    """ขอดูระดับสูงกว่าระดับตัวเอง (เกิน band) → ว่าง / ถูกตัด (fail-closed)"""
    w = grade_world
    m4 = w["rooms"]["ม.4"]["room_id"]
    m5 = w["rooms"]["ม.5"]["room_id"]

    lvl_m4 = _post_issue(client, w["m4_student"]["token"], m4, title="เรื่องระดับ ม.4")
    await _promote_level(db_pool, lvl_m4, "level")
    council_issue = _post_issue(client, w["admin"]["token"], m4, title="เรื่องสภา", start="council")
    room_m5 = _post_issue(client, w["m5_student"]["token"], m5, title="เรื่องห้อง ม.5")

    # ประธานระดับขอ levels=council → band ของ level ไม่มี council → ว่าง (ทั้งที่ council มีเรื่องจริง)
    body = _list(client, w["m4_level"]["token"], received="true", levels="council").json()
    assert body["items"] == []

    # หัวหน้าห้อง (room) ขอดูระดับ level → ว่าง (มองขึ้นไม่ได้)
    code = w["rooms"]["ม.4"]["room_code"]
    sid = f"R{random.randint(1000, 9999)}HD"
    uid = await auth_service.register_user(
        db_pool, sid, "1234", "หัวหน้า ห้อง", sid, code, 5, "class_president"
    )
    head_token = auth_service.create_access_token(uid)
    body = _list(client, head_token, received="true", levels="level").json()
    assert body["items"] == []
    assert room_m5 not in {i["id"] for i in body["items"]}


@pytest.mark.asyncio
async def test_received_invalid_levels_400(client, grade_world):
    """levels ที่ไม่รู้จัก (banana) → 400 — validate ฝั่ง router"""
    w = grade_world
    res = _list(client, w["admin"]["token"], received="true", levels="banana")
    assert res.status_code == 400
    res = _list(client, w["admin"]["token"], received="true", levels="room,council,xxx")
    assert res.status_code == 400
