# === Responsibilities (หน้าที่) + User Management (manual add / hierarchy) ===
# - responsibilities: JSONB array บน students — เฉพาะ council_member / level_vice_president
# - GET /students: ประธานระดับเห็นได้เฉพาะระดับชั้นตัวเอง + role ที่จัดการได้ (ไม่เห็น role สูงกว่า)
# - PATCH /students/{id}: แก้ role/หน้าที่ — ต้องไม่เกิน hierarchy (rank)
# - POST /students: manual add — ตรวจ grade scope + hierarchy + validate หน้าที่
import json
import random

import pytest
import pytest_asyncio

from services import auth_service


@pytest_asyncio.fixture
async def manage_world(db_pool):
    """ม.4 + ม.5: ประธานระดับ ม.4 (m4_level), สภานักเรียน ม.4 (council_member),
    นักเรียน ม.4 (m4_student), นักเรียน ม.5 (m5_student), admin (council_president, is_admin)"""
    rooms = {}
    for level_lbl in ("ม.4", "ม.5"):
        code = f"ห{random.randint(100, 999)}/{level_lbl[-1]}"
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
        ("council_member", "council_member", "ม.4", 3),
        ("m5_student", "student", "ม.5", 1),
    ]:
        sid = f"M{random.randint(1000, 9999)}{label[:2].upper()}"
        uid = await auth_service.register_user(
            db_pool, sid, "1234", f"{label} ทดสอบ", sid,
            rooms[level_lbl]["room_code"], no, role
        )
        users[label] = {"user_id": uid, "token": auth_service.create_access_token(uid)}

    sid = f"M{random.randint(1000, 9999)}AD"
    uid = await auth_service.register_user(
        db_pool, sid, "1234", "แอดมิน ทดสอบ", sid, rooms["ม.4"]["room_code"], 9,
        "council_president"
    )
    users["admin"] = {"user_id": uid, "token": auth_service.create_access_token(uid)}

    users["rooms"] = rooms
    return users


async def _student_row_id(db_pool, user_id):
    async with db_pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT id FROM students WHERE user_id = $1 AND deleted_at IS NULL ORDER BY id LIMIT 1",
            user_id
        )


async def _student_responsibilities(db_pool, student_id):
    async with db_pool.acquire() as conn:
        raw = await conn.fetchval(
            "SELECT responsibilities FROM students WHERE id = $1", student_id
        )
    if isinstance(raw, str):
        return json.loads(raw)
    return list(raw or [])


def _patch(client, token, student_id, payload):
    return client.patch(f"/api/students/{student_id}", json=payload,
                        headers={"Authorization": f"Bearer {token}"})


# ============================================================
# 1) แก้ responsibilities (ผ่าน PATCH /students)
# ============================================================
@pytest.mark.asyncio
async def test_update_responsibilities_valid(client, manage_world, db_pool):
    """admin ตั้งหน้าที่ให้ council_member ได้ → deep-DB ตรวจค่า JSONB"""
    w = manage_world
    sid = await _student_row_id(db_pool, w["council_member"]["user_id"])

    res = _patch(client, w["admin"]["token"], sid,
                 {"responsibilities": ["academic", "discipline"]})
    assert res.status_code == 200, res.text
    assert await _student_responsibilities(db_pool, sid) == ["academic", "discipline"]

    # แก้ซ้ำ/ลดได้ (การ์ด: ตัดซ้ำ, keep order)
    res = _patch(client, w["admin"]["token"], sid,
                 {"responsibilities": ["activity", "academic", "activity"]})
    assert res.status_code == 200
    assert await _student_responsibilities(db_pool, sid) == ["activity", "academic"]


@pytest.mark.asyncio
async def test_update_responsibilities_invalid_code(client, manage_world, db_pool):
    """หมวดหน้าที่ที่ไม่ใช่ 9 หมวดจริง → 400"""
    w = manage_world
    sid = await _student_row_id(db_pool, w["council_member"]["user_id"])
    res = _patch(client, w["admin"]["token"], sid, {"responsibilities": ["hacker"]})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_update_responsibilities_rejected_for_non_responsible_role(client, manage_world, db_pool):
    """role ที่ไม่มีหน้าที่ (student) → ตั้ง responsibilities ไม่ได้ (400)"""
    w = manage_world
    sid = await _student_row_id(db_pool, w["m4_student"]["user_id"])
    res = _patch(client, w["admin"]["token"], sid, {"responsibilities": ["academic"]})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_role_change_clears_responsibilities(client, manage_world, db_pool):
    """ย้าย council_member → role ที่ไม่มีหน้าที่ → responsibilities ถูกเคลียร์"""
    w = manage_world
    sid = await _student_row_id(db_pool, w["council_member"]["user_id"])

    assert _patch(client, w["admin"]["token"], sid,
                  {"responsibilities": ["academic"]}).status_code == 200
    res = _patch(client, w["admin"]["token"], sid, {"class_role": "student"})
    assert res.status_code == 200
    assert await _student_responsibilities(db_pool, sid) == []


# ============================================================
# 2) Manual Add (POST /students) — + ตรวจ roles /auth/me
# ============================================================
@pytest.mark.asyncio
async def test_manual_add_level_vice_president(client, manage_world, db_pool):
    """admin เพิ่มผู้ช่วยหัวหน้าระดับ + หน้าที่ → 201 + deep-DB + /auth/me เห็น responsibilities"""
    w = manage_world
    code = w["rooms"]["ม.4"]["room_code"]
    username = f"NEW{random.randint(1000, 9999)}"

    res = client.post("/api/students", json={
        "username": username, "password": "1234",
        "first_name": "ใหม่", "last_name": "เพิ่ม",
        "room_code": code, "class_role": "level_vice_president",
        "responsibilities": ["discipline"],
    }, headers={"Authorization": f"Bearer {w['admin']['token']}"})
    assert res.status_code == 201, res.text

    # deep-DB: user + student + responsibilities + permissions (จาก config roles)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT s.id, s.class_role, s.responsibilities, s.is_admin,
                   s.permissions, u.id AS user_id
            FROM students s JOIN users u ON u.id = s.user_id
            WHERE u.username = $1 AND s.deleted_at IS NULL
            """,
            username
        )
    assert row is not None
    assert row["class_role"] == "level_vice_president"
    resp = row["responsibilities"]
    if isinstance(resp, str):
        resp = json.loads(resp)
    assert resp == ["discipline"]
    perms = row["permissions"]
    if isinstance(perms, str):
        perms = json.loads(perms)
    assert "MANAGE_STUDENTS" in perms  # ผู้ช่วยหัวหน้าระดับได้สิทธิ์นี้ (เหมือนประธานระดับ)

    # /auth/me: roles[].responsibilities ต้องออกมาด้วย (frontend กรองตามหน้าที่)
    new_token = auth_service.create_access_token(row["user_id"])
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me.status_code == 200
    role_infos = me.json()["roles"]
    assert any(
        r["role"] == "level_vice_president" and r["responsibilities"] == ["discipline"]
        for r in role_infos
    )


@pytest.mark.asyncio
async def test_manual_add_duplicate_username(client, manage_world, db_pool):
    """username ซ้ำ (มีอยู่แล้ว) → 409"""
    w = manage_world
    dup_user = await _student_row_id(db_pool, w["m4_student"]["user_id"])
    async with db_pool.acquire() as conn:
        dup_username = await conn.fetchval(
            "SELECT username FROM users WHERE id = (SELECT user_id FROM students WHERE id = $1)",
            dup_user
        )
    res = client.post("/api/students", json={
        "username": dup_username, "password": "1234", "first_name": "ซ้ำ",
        "room_code": w["rooms"]["ม.4"]["room_code"], "class_role": "student",
    }, headers={"Authorization": f"Bearer {w['admin']['token']}"})
    assert res.status_code == 409


# ============================================================
# 3) Hierarchy + grade scope ของการจัดการ (PATCH/POST)
# ============================================================
@pytest.mark.asyncio
async def test_level_role_cannot_edit_higher_rank(client, manage_world, db_pool):
    """ประธานระดับ (rank 2) แก้ไขสภานักเรียน (rank 3) → 403"""
    w = manage_world
    council_sid = await _student_row_id(db_pool, w["council_member"]["user_id"])

    res = _patch(client, w["m4_level"]["token"], council_sid,
                 {"class_role": "student"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_level_role_cannot_promote_to_higher_rank(client, manage_world, db_pool):
    """ประธานระดับ (rank 2) ยกระดับ นักเรียน → สภานักเรียน (rank 3) → 403"""
    w = manage_world
    student_sid = await _student_row_id(db_pool, w["m4_student"]["user_id"])
    res = _patch(client, w["m4_level"]["token"], student_sid,
                 {"class_role": "council_member"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_level_role_edits_own_grade_responsible_role(client, manage_world, db_pool):
    """ประธานระดับแก้หน้าที่ให้ผู้ช่วยหัวหน้าระดับ (rank 2 = เท่ากัน, ชั้น ม.4) → ได้"""
    w = manage_world
    code = w["rooms"]["ม.4"]["room_code"]

    # สร้าง ผู้ช่วยหัวหน้าระดับ ม.4 (ด้วย admin — school-wide)
    uname = f"VP{random.randint(1000, 9999)}"
    add = client.post("/api/students", json={
        "username": uname, "password": "1234", "first_name": "ผู้ช่วย",
        "room_code": code, "class_role": "level_vice_president",
        "responsibilities": [],
    }, headers={"Authorization": f"Bearer {w['admin']['token']}"})
    assert add.status_code == 201
    vp_sid = add.json()["student_id"]

    # ประธานระดับ ม.4 ตั้งหน้าที่ให้ผู้ช่วย ม.4 ได้
    res = _patch(client, w["m4_level"]["token"], vp_sid,
                 {"responsibilities": ["activity", "reception"]})
    assert res.status_code == 200, res.text
    assert await _student_responsibilities(db_pool, vp_sid) == ["activity", "reception"]


@pytest.mark.asyncio
async def test_level_role_cannot_add_to_other_grade(client, manage_world):
    """ประธานระดับ ม.4 เพิ่มผู้ใช้ห้อง ม.5 → 403 (grade scope)"""
    w = manage_world
    res = client.post("/api/students", json={
        "username": f"X{random.randint(1000, 9999)}", "password": "1234",
        "first_name": "ข้าม", "room_code": w["rooms"]["ม.5"]["room_code"],
        "class_role": "student",
    }, headers={"Authorization": f"Bearer {w['m4_level']['token']}"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_students_grade_scoped_for_level_role(client, manage_world, db_pool):
    """GET /students ของประธานระดับ ม.4 → เห็นเฉพาะคนชั้น ม.4 ที่ role ≤ ตนเอง
    (ไม่เห็น ม.5, ไม่เห็น council_member/admin ที่เป็น role สูงกว่า)"""
    w = manage_world
    res = client.get("/api/students", headers={"Authorization": f"Bearer {w['m4_level']['token']}"})
    assert res.status_code == 200
    body = res.json()
    room_codes = {s["room_code"] for s in body}
    roles = {s["class_role"] for s in body}
    m4_code = w["rooms"]["ม.4"]["room_code"]
    m5_code = w["rooms"]["ม.5"]["room_code"]

    # ทุกคนที่เห็นอยู่ในชั้น ม.4 เท่านั้น
    assert room_codes == {m4_code}
    assert m5_code not in room_codes
    # และเห็นได้เฉพาะ role ที่ต่ำกว่า/เท่ากับตัวเอง (rank ≤ 2) — ไม่เห็น council_member/admin
    assert "council_member" not in roles
    assert "student" in roles
    assert "level_president" in roles


@pytest.mark.asyncio
async def test_get_students_school_wide_sees_all(client, manage_world):
    """admin เห็นทุกคนทุกชั้น (school-wide)"""
    w = manage_world
    res = client.get("/api/students", headers={"Authorization": f"Bearer {w['admin']['token']}"})
    assert res.status_code == 200
    room_codes = {s["room_code"] for s in res.json()}
    assert w["rooms"]["ม.4"]["room_code"] in room_codes
    assert w["rooms"]["ม.5"]["room_code"] in room_codes


@pytest.mark.asyncio
async def test_council_member_cannot_use_user_management(client, manage_world):
    """สภานักเรียน (ไม่มี MANAGE_STUDENTS) → GET /students 403"""
    w = manage_world
    res = client.get("/api/students", headers={"Authorization": f"Bearer {w['council_member']['token']}"})
    assert res.status_code == 403


# ============================================================
# 👑 ตำแหน่งพิเศษที่ไม่ได้สังกัดห้อง (room_id NULL) — ต้องเห็น/จัดการได้ในหน้า จัดการสมาชิก
# (admin / ครูสภา / ประธานสภา / สภานักเรียน ถูกสร้างแบบไม่ผูกห้อง เหมือน seed_users)
# Fix: เดิม list_students ใช้ INNER JOIN rooms → ตัดสมาชิก room-less ทิ้ง → เปลี่ยนเป็น LEFT JOIN
# ============================================================
async def _make_roomless(db_pool, username: str, full_name: str, role: str, no: int) -> dict:
    """สร้าง user + student แบบ room-less (room_id NULL) ตาม pattern seed_users"""
    uid = await auth_service.register_user(
        db_pool, username, "1234", full_name, username, None, no, role
    )
    return {"user_id": uid, "token": auth_service.create_access_token(uid)}


@pytest.mark.asyncio
async def test_school_wide_sees_roomless_special_members(client, db_pool):
    """ประธานสภา (room-less, is_admin) เห็นสมาชิกตำแหน่งพิเศษ room-less ทั้งหมดใน GET /students
    — แก้ bug: หน้า จัดการสมาชิก กลุ่ม 'สภานักเรียน' ว่าง เพราะ INNER JOIN ตัดคนที่ไม่ได้สังกัดห้องทิ้ง"""
    actor = await _make_roomless(db_pool, f"act{random.randint(1000, 9999)}", "ประธานสภา ทดสอบ", "council_president", 1)
    await _make_roomless(db_pool, f"adm{random.randint(1000, 9999)}", "แอดมิน ทดสอบ", "admin", 2)
    await _make_roomless(db_pool, f"tch{random.randint(1000, 9999)}", "ครูสภา ทดสอบ", "teacher_council", 3)
    await _make_roomless(db_pool, f"mem{random.randint(1000, 9999)}", "สภานักเรียน ทดสอบ", "council_member", 4)

    res = client.get("/api/students", headers={"Authorization": f"Bearer {actor['token']}"})
    assert res.status_code == 200, res.text
    body = res.json()
    roles = {s["class_role"] for s in body}

    # ต้องเห็นทุกตำแหน่งพิเศษ room-less (รวมตัวเอง) — ไม่ใช่เห็นแค่คนที่มีห้อง
    assert {"council_president", "admin", "teacher_council", "council_member"} <= roles, (
        f"ตำแหน่งพิเศษ room-less หายจากรายการ (กลุ่มสภานักเรียนจะว่าง) → {sorted(roles)}"
    )
    # สมาชิกที่เห็นเป็น room-less ล้วน (room_code None) — ยังแสดงผล/แก้ไขได้ตามปกติ
    assert all(s["room_code"] is None for s in body), body


@pytest.mark.asyncio
async def test_grade_scoped_manager_never_sees_roomless(client, manage_world, db_pool):
    """ประธานระดับ ม.4 ยังต้องไม่เห็นตำแหน่งพิเศษ room-less (LEFT JOIN ไม่รั่วขอบเขตระดับชั้น)"""
    w = manage_world
    # เพิ่มตำแหน่งพิเศษ room-less เข้าระบบ — ควรเห็นเฉพาะผู้จัดการ school-wide เท่านั้น
    await _make_roomless(db_pool, f"sc{random.randint(1000, 9999)}", "คนสภา ทดสอบ", "council_president", 9)

    res = client.get("/api/students", headers={"Authorization": f"Bearer {w['m4_level']['token']}"})
    assert res.status_code == 200, res.text
    body = res.json()
    # ทุกคนที่ประธานระดับเห็นต้องมีห้อง และเป็นห้องชั้น ม.4 เท่านั้น (ไม่เห็น room-less/คนต่างชั้น)
    assert body, "ประธานระดับ ม.4 ควรเห็นสมาชิกชั้น ม.4 อย่างน้อย 1 คน"
    assert all(s["room_id"] is not None for s in body)
    assert {s["room_code"] for s in body} == {w["rooms"]["ม.4"]["room_code"]}


# ============================================================
# 🚫 ไม่ตัด LIMIT 500 — ผู้จัดการ school-wide ต้องเห็นสมาชิกทั้งโรงเรียนเกิน 500 คน
# (Bug จริงตอน production: list_students hardcode LIMIT 500 + ORDER BY room_code
#  → 500 คนแรกที่ได้ = ห้อง ม.1 ทั้งหมด → ครู/Admin (room-less) เห็นแค่ "นักเรียน ม.1 จำนวน 500")
# Fix: limit default = None (ไม่ตัด) — หน้า User Management กรอง group/search client-side ต้องได้ทั้งชุด
# ============================================================
@pytest.mark.asyncio
async def test_school_wide_roster_over_500_not_truncated(client, db_pool):
    """ผู้จัดการ school-wide (room-less) เห็นสมาชิกเกิน 500 คนครบทุกคนทุกชั้น
    — รวมคนห้อง ม.2 ที่อยู่นอก 500 คนแรก (เคยถูก LIMIT 500 ตัดหาย = เห็นแค่ ม.1)"""
    actor = await _make_roomless(db_pool, f"boss{random.randint(1000, 9999)}", "ประธานสภา ทดสอบ", "council_president", 1)

    # โครงสร้างห้อง: ม.1 หลายห้อง (520 คน) เรียงก่อนตาม room_code + ม.2 หนึ่งห้อง (30 คน) คั่นท้าย
    # ถ้ายังตัด LIMIT 500 → 500 คนแรก = ม.1 ล้วน → ห้อง ม.2 หายไปทั้งห้อง
    specs = [
        ("M1-01", "ม.1", 65), ("M1-02", "ม.1", 65), ("M1-03", "ม.1", 65), ("M1-04", "ม.1", 65),
        ("M1-05", "ม.1", 65), ("M1-06", "ม.1", 65), ("M1-07", "ม.1", 65), ("M1-08", "ม.1", 65),
        ("M2-01", "ม.2", 30),
    ]
    m2_code = "M2-01"
    total = sum(n for _, _, n in specs)

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # users (ฝาก raw — password ไม่ต้อง hash เพราะไม่มีการ login ในเทสต์)
            await conn.execute(
                "INSERT INTO users (username, password_hash, full_name) "
                "SELECT 'bulk' || g, 'x', 'คนที่' || g FROM generate_series(1, $1) g",
                total
            )
            user_ids = [r["id"] for r in await conn.fetch(
                "SELECT id FROM users WHERE username LIKE 'bulk%' ORDER BY id"
            )]
            assert len(user_ids) == total

            # rooms + แบ่ง user ใส่ห้องตาม spec
            room_slots = []  # (room_id, count) เรียงตามลำดับที่จะถูก ORDER BY room_code
            slot_of_user = []  # room_id ต่อ user_index
            for code, level, n in specs:
                rid = await conn.fetchval(
                    "INSERT INTO rooms (room_code, room_name, level) VALUES ($1, $2, $3) RETURNING id",
                    code, f"ห้อง {code}", level
                )
                room_slots.extend([rid] * n)
            for idx, rid in enumerate(room_slots):
                slot_of_user.append(rid)

            await conn.executemany(
                "INSERT INTO students (room_id, user_id, student_id, student_no, first_name, class_role, status) "
                "VALUES ($1, $2, $3, $4, $5, 'student', 'active')",
                [
                    (slot_of_user[i], uid, f"S{i + 1:04d}", (i % 50) + 1, f"คน{i + 1}")
                    for i, uid in enumerate(user_ids)
                ]
            )

    # จำนวนจริงใน DB (550 bulk + actor + บัญชี seed เริ่มต้นของ conftest) — ห้ามตัดทิ้งเหลือ 500
    async with db_pool.acquire() as conn:
        expected = await conn.fetchval(
            "SELECT count(*) FROM students WHERE deleted_at IS NULL"
        )
    assert expected > 500, "โครงเทสต์ต้องมีสมาชิกเกิน 500 คนจริง ๆ (ไม่เช่นนั้นวัดผล LIMIT ไม่ได้)"

    res = client.get("/api/students", headers={"Authorization": f"Bearer {actor['token']}"})
    assert res.status_code == 200, res.text
    body = res.json()

    # ต้องได้ครบทั้งชุด (expected) — ไม่ถูกตัดที่ 500 (ขอ check 500 คนแรกที่เป็น ม.1)
    assert len(body) == expected, (
        f"รายชื่อถูกตัดเหลือ {len(body)}/{expected} คน → LIMIT ยังตัดอยู่ "
        f"(โรงเรียนเกิน 500 คน แล้ว teacher/Admin เห็นแค่ 500 คนแรก)"
    )
    # และต้องเห็นนักเรียนห้อง ม.2 (คนที่เกิน 500 แรก) — ไม่งั้น = เห็นแค่ ม.1 เหมือน bug เดิม
    codes = {s["room_code"] for s in body}
    assert m2_code in codes, (
        f"ไม่เห็นสมาชิกห้อง {m2_code} (เลย 500 คนแรก) → ยังถูกตัดเหลือแค่ห้อง ม.1: {sorted(codes)}"
    )
