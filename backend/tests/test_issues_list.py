# === Issue List Tests: Pagination + Search + Sort ===
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


def _list(client, token, **params):
    return client.get("/api/issues", params=params,
                      headers={"Authorization": f"Bearer {token}"})


# === Section 1: Pagination ===
@pytest.mark.asyncio
async def test_issues_list_pagination(client, issue_world):
    """GET /api/issues ต้องคืน envelope {items,total,page,page_size,pages} แบ่งหน้าถูกต้อง"""
    users = issue_world
    student = users["student"]

    # สร้าง 7 เรื่อง (มองเห็นทั้งหมดด้วย student)
    for n in range(7):
        res = _create_issue(client, users, title=f"เรื่องที่ {n}")
        assert res.status_code == 200

    token = student["token"]
    # หน้า 1: limit=3 → ได้ 3 items, total=7, page=1, pages=3
    res = _list(client, token, limit=3, offset=0)
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 3
    assert body["total"] == 7
    assert body["page"] == 1
    assert body["page_size"] == 3
    assert body["pages"] == 3

    # หน้าสุดท้าย: offset=6 → เหลือ 1 เรื่อง
    res = _list(client, token, limit=3, offset=6)
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1
    assert res.json()["page"] == 3

    # เลยหน้า → ว่าง แต่ total ยังครบ
    res = _list(client, token, limit=3, offset=9)
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 0
    assert body["total"] == 7
    assert body["pages"] == 3


@pytest.mark.asyncio
async def test_issues_list_pagination_defaults(client, issue_world):
    """ไม่ส่ง limit/offset → limit default 100, page=1, pages=1"""
    users = issue_world
    res = _create_issue(client, users, title="เรื่องเดียว")
    assert res.status_code == 200

    body = _list(client, users["student"]["token"]).json()
    assert len(body["items"]) == 1
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 100
    assert body["pages"] == 1


# === Section 2: Search (คำต่อคำ ILIKE) ===
@pytest.mark.asyncio
async def test_issues_search_title(client, issue_world):
    """q= เจอเรื่องที่ชื่อเรื่องมีคำนั้น (ไม่เจอเรื่องอื่น)"""
    users = issue_world
    assert _create_issue(client, users, title="พัดลมเสียในห้องเรียน").status_code == 200
    assert _create_issue(client, users, title="หลอดไฟห้องน้ำพัง").status_code == 200

    body = _list(client, users["student"]["token"], q="พัดลม").json()
    items = body["items"]
    assert len(items) == 1
    assert items[0]["title"] == "พัดลมเสียในห้องเรียน"


@pytest.mark.asyncio
async def test_issues_search_description(client, issue_world):
    """q= เจอเรื่องที่คำอธิบายมีคำนั้น"""
    users = issue_world
    assert _create_issue(client, users, title="เรื่อง A", desc="อยากให้ปรับปรุงสนามฟุตบอล").status_code == 200
    assert _create_issue(client, users, title="เรื่อง B", desc="อยากให้เพิ่มที่จอดรถ").status_code == 200

    body = _list(client, users["student"]["token"], q="สนามฟุตบอล").json()
    items = body["items"]
    assert len(items) == 1
    assert items[0]["title"] == "เรื่อง A"


@pytest.mark.asyncio
async def test_issues_search_room(client, issue_world, db_pool):
    """q= ชื่อห้อง → เจอเรื่องที่อยู่ในห้องนั้น (ไม่เจอห้องอื่น)"""
    users = issue_world

    # สร้างห้อง ม.5 เพิ่มอีกห้อง
    room2_code = f"ม.5/{random.randint(1, 90)}"
    async with db_pool.acquire() as conn:
        room2_id = await conn.fetchval(
            "INSERT INTO rooms (room_code, room_name, level) VALUES ($1,$2,'ม.5') RETURNING id",
            room2_code, room2_code
        )

    assert _create_issue(client, users, title="เรื่องห้องเดิม", room_id=users["student"]["room_id"]).status_code == 200
    assert _create_issue(client, users, title="เรื่องห้อง ม.5", room_id=room2_id).status_code == 200

    body = _list(client, users["student"]["token"], q=room2_code).json()
    items = body["items"]
    assert len(items) == 1
    assert items[0]["title"] == "เรื่องห้อง ม.5"


@pytest.mark.asyncio
async def test_issues_search_reporter_name(client, issue_world, db_pool):
    """q= ชื่อผู้แจ้ง → เจอเรื่องที่ผู้แจ้งชื่อนั้น (reporter_name snapshot จาก students)"""
    users = issue_world
    student = users["student"]

    # register_user เขียน first/last name ว่าง → ตั้งชื่อจริงให้ก่อนสร้างเรื่อง
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE students SET first_name = 'สมชาย', last_name = 'ใจดี' WHERE user_id = $1",
            student["user_id"]
        )
    assert _create_issue(client, users, title="เรื่องของสมชาย").status_code == 200
    assert _create_issue(client, users, title="เรื่องของคนอื่น", token=users["head"]["token"]).status_code == 200

    body = _list(client, student["token"], q="สมชาย").json()
    items = body["items"]
    assert len(items) == 1
    assert items[0]["title"] == "เรื่องของสมชาย"


@pytest.mark.asyncio
async def test_issues_search_multi_token_and(client, issue_world):
    """q= หลายคำ (เว้นวรรค) → ต้องมีครบทุกคำในอย่างน้อย 1 ฟิลด์"""
    users = issue_world
    assert _create_issue(client, users, title="น้ำท่วม ห้องน้ำ ชั้น 2").status_code == 200
    assert _create_issue(client, users, title="น้ำท่วม สนามหลังโรงเรียน").status_code == 200

    body = _list(client, users["student"]["token"], q="น้ำท่วม ชั้น").json()
    items = body["items"]
    assert len(items) == 1
    assert items[0]["title"] == "น้ำท่วม ห้องน้ำ ชั้น 2"


@pytest.mark.asyncio
async def test_issues_search_escapes_wildcard(client, issue_world):
    r"""ตัวอักษร % _ \ ต้องถูกหนี — q=% ต้องเจอเฉพาะเรื่องที่มี % จริง ไม่ใช่ wildcard ทุกเรื่อง"""
    users = issue_world
    assert _create_issue(client, users, title="ผ่านไป 100% ของงาน").status_code == 200
    assert _create_issue(client, users, title="งานเสร็จเรียบร้อย").status_code == 200

    body = _list(client, users["student"]["token"], q="%").json()
    items = body["items"]
    assert len(items) == 1
    assert items[0]["title"] == "ผ่านไป 100% ของงาน"


@pytest.mark.asyncio
async def test_issues_search_respects_visibility(client, issue_world):
    """ค้นหาในขอบเขตตัวเอง — student ต้องไม่เจอเรื่องของคนอื่นที่มีคำเดียวกัน"""
    users = issue_world
    assert _create_issue(client, users, title="ห้องน้ำพัง").status_code == 200  # ของ student
    assert _create_issue(client, users, title="ห้องน้ำพังเช่นกัน", token=users["head"]["token"]).status_code == 200  # ของ head

    # student เห็นแค่เรื่องตัวเอง (พีระมิด: i.reporter_id = student)
    body = _list(client, users["student"]["token"], q="ห้องน้ำพัง").json()
    items = body["items"]
    assert len(items) == 1
    assert items[0]["reporter_id"] == users["student"]["user_id"]

    # head (ระดับ room มองลงเห็นเรื่องระดับล่าง + ของตัวเอง) → เห็นทั้ง 2
    body = _list(client, users["head"]["token"], q="ห้องน้ำพัง").json()
    assert len(body["items"]) == 2


# === Section 3: Sort ===
@pytest.mark.asyncio
async def test_issues_sort_asc_desc(client, issue_world):
    """sort=asc เรียงเก่า→ใหม่ (ตาม created_at, id รอง), sort=desc (default) ใหม่→เก่า"""
    users = issue_world
    token = users["student"]["token"]

    ids = []
    for title in ("เรื่องแรก", "เรื่องที่สอง", "เรื่องที่สาม"):
        res = _create_issue(client, users, title=title)
        assert res.status_code == 200
        ids.append(res.json()["id"])

    # asc: เก่าไปใหม่
    body = _list(client, token, sort="asc").json()
    assert [i["id"] for i in body["items"]] == ids

    # desc (default): ใหม่ไปเก่า
    body = _list(client, token).json()
    assert [i["id"] for i in body["items"]] == list(reversed(ids))
    body = _list(client, token, sort="desc").json()
    assert [i["id"] for i in body["items"]] == list(reversed(ids))


@pytest.mark.asyncio
async def test_issues_sort_invalid(client, issue_world):
    """sort ที่ไม่ใช่ asc/desc → 422 (pattern validation)"""
    res = _list(client, issue_world["student"]["token"], sort="abc")
    assert res.status_code == 422
