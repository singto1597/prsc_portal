# 🏫 PRSC Portal — Lessons จากพัฒนาระบบรับความคิดเห็นและปัญหา

> ส่วนนี้บันทึกบทเรียนที่เจอจริงระหว่างพัฒนาระบบ PRSC Portal (สภานักเรียน) ตั้งแต่โครงสร้าง → backend → frontend → deploy

### 🛠️ asyncpg AmbiguousParameterError — `$1` ซ้ำใน 2 คอลัมน์คนละ type
- **Context/Problem:** `INSERT INTO rooms (room_code, room_name) VALUES ($1,$1)` → `AmbiguousParameterError: inconsistent types deduced for parameter $1` (VARCHAR vs TEXT) และ `INSERT has more expressions than target columns` เมื่อ parameter count ไม่ตรงคอลัมน์
- **Root Cause:** asyncpg อนุมาน type ของ parameter จากบริบท — ใช้ `$1` ตัวเดียวกับ 2 คอลัมน์ที่ type ต่างกัน (หรือ count ผิด) จะพังทั้งตอน runtime และตอน seed
- **Correct Pattern/Solution:** ใช้ parameter แยกเสมอ `VALUES ($1,$2,$3)`; นับจำนวน `$n` ให้ตรงกับคอลัมน์+values ก่อนรัน; โดยเฉพาะใน `seed_data.py`/script ที่มือเขียน SQL ตรงๆ — อาการเดาได้จาก error `INSERT has more expressions`
- **Date Added:** 2026-08-08

### 🛠️ FastAPI Router + asyncpg — ต้องมี `python-multipart` สำหรับ `UploadFile`/Form
- **Context/Problem:** Import Excel ผ่าน `UploadFile` → RuntimeError: `Form data requires "python-multipart" to be installed` เฉพาะตอน import router ตัวนั้น
- **Root Cause:** FastAPI ติดตั้ง multipart parser ตอน declare `UploadFile` — ถ้า package ไม่มี จะ error ที่ import ไม่ใช่ runtime
- **Correct Pattern/Solution:** เพิ่ม `python-multipart>=0.0.9` ใน `requirements.txt` ตั้งแต่วันแรก (เวลา scaffold โปรเจค FastAPI ใหม่ + file upload ให้ใส่เลย)
- **Date Added:** 2026-08-08

### 🛠️ Frontend API baseURL — ต้องมี `/api` prefix ครบทุก service
- **Context/Problem:** login ผ่าน API ตรง (curl) ได้ แต่หน้าเว็บได้ "Not Found" ทุกบัญชี — backend ประกาศ endpoint `/api/auth/login` แต่ frontend ส่งไป `/auth/login`
- **Root Cause:** สร้าง `services/*.ts` แล้วลืม prefix `/api` (backend ใช้ `prefix="/api"` ใน main.py)
- **Correct Pattern/Solution:** grep ตรวจ `api.get('/` / `api.post('/` ให้ขึ้นต้น `/api/` เสมอ; เมื่อสร้าง service ใหม่ให้ตรวจ 1 ครั้ง — ผูกกับบทเรียนเดิม "ทุก layer ต้องรู้ path prefix"
- **Date Added:** 2026-08-08

### 🛠️ asyncpg `IndeterminateDatatypeError` — parameter เกินใน SQL ที่สร้าง dynamic
- **Context/Problem:** `GET /api/issues?mine=true` → 500 `could not determine data type of parameter $1`; เหตุผล: `list_issues` สร้าง `visible_cond` (เพิ่ม params) เสมอ แม้ `only_mine` ไม่ใช้มัน → มี `$1` เกินใน SQL
- **Root Cause:** สร้าง WHERE condition + params แล้วไม่ใช้ทุกตัว — asyncpg ตี type ไม่ได้เพราะ parameter ไม่อ้างถึง
- **Correct Pattern/Solution:** สร้าง dynamic WHERE + params **พร้อมกันเฉพาะ branch ที่ใช้** (ไม่สร้างล่วงหน้าแล้วทิ้ง); ก่อน `conn.fetch(sql, *params)` ตรวจ `sql.count('$') == len(params)` คร่าวๆ; พอเจอ 500 ดู traceback บรรทัด fetch แล้วไล่ count parameter
- **Date Added:** 2026-08-08

### 🛠️ RBAC — แยก `require_permission` (ระดับห้อง) vs `require_permission_anywhere` (ข้ามห้อง)
- **Context/Problem:** ตอนแรก define `require_permission` ซ้ำใน router (hacky) — ต้องย้ายไป core และแยกความหมาย 2 แบบ
- **Root Cause:** สิทธิ์ระดับโรงเรียน (MANAGE_STUDENTS, VIEW_DASHBOARD) ไม่ผูกกับห้องเดียว — เช็ค `require_permission(conn, room_id, ...)` จะ fail เพราะไม่มี room ที่ตรง
- **Correct Pattern/Solution:**
  1. `core/rbac.py`: `require_permission(conn, room_id, user_id, perm)` — ระดับห้อง (ดู is_admin/permissions ใน students ของห้องนั้น)
  2. `require_permission_anywhere(conn, user_id, perm)` — วนทุก membership ที่ active, is_admin ผ่าน, มี perm ใน role ไหนก็ผ่าน
  3. Router import จาก core เสมอ — **ห้าม** re-define helper ใน router
- **Date Added:** 2026-08-08

### 🛠️ Role → Permissions ต้องมาจาก config/roles.json (ไม่ hardcode ใน DB)
- **Context/Problem:** ตอนแรกทุกคน permissions ว่าง → frontend ซ่อนเมนูไม่ได้ (Dashboard โผล่ให้ทุกคนแม้เด้ง)
- **Root Cause:** register/import/seed ไม่ได้ตั้ง `students.permissions` ตามตำแหน่ง
- **Correct Pattern/Solution:**
  1. `core/rbac.get_role_permissions(role)` อ่าน `config/roles.json` (`roles[role].permissions`) แล้วแคชครั้งแรก
  2. ทุกจุดที่ create/update student (register_user, import Excel, seed) ต้องตั้ง `permissions = json.dumps(get_role_permissions(class_role))`
  3. frontend ใช้ `authStore.hasPermission(...)` + `isAdmin` เพื่อซ่อนเมนู และ router `meta.requiresPermission` guard กันเข้า URL ตรง
- **Date Added:** 2026-08-08

### 🛠️ Pyramid Escalation — visibility "มองลง" ไม่ใช่แค่ระดับตัวเอง
- **Context/Problem:** ตอนแรกหน้า "เรื่องที่รับ" โชว์แค่ระดับตัวเอง; ตาม requirement ระดับสูงควรเห็นทุกระดับล่าง (พีระมิด) + กรองระดับได้
- **Correct Pattern/Solution:**
  1. `LEVEL_RANK = {"student":0,"room":1,"level":2,"council":3}` — student เป็นระดับต่ำสุด (ใช้ `.index()` กับ list ที่ไม่มี student → ValueError)
  2. `can_see(level, issue_level, reporter_id, user_id, is_anonymous)` — ระดับสูง ≥ ระดับเรื่อง = เห็น; ผู้แจ้งเห็นเรื่องตัวเองเสมอ (แม้ anonymous — anonymity ซ่อนชื่อคนอื่น ไม่ใช่ซ่อนจากเจ้าของ)
  3. Query ใช้ `CASE i.current_level WHEN 'room' THEN 1 ...` เปรียบเทียบตัวเลข (ห้ามเปรียบเทียบ string lexicographic)
  4. "เรื่องที่เกี่ยวข้อง" (เคยรับ/escalate จากห้องตัวเอง) ต้องเห็นแม้โดนส่งขึ้นไปแล้ว — เช็คผ่าน `issue_escalations.from_assignee_id` / `issue_countdowns.assignee_id`
- **Date Added:** 2026-08-08

### 🛠️ start_level — ผู้แจ้งระดับสูงเลือกเริ่มต้นเรื่องที่ระดับสูงขึ้นได้
- **Context/Problem:** หัวหน้าห้อง/ประธานระดับ/สภาที่เป็นคนแจ้ง ไม่อยากแจ้งแล้วค่อยกดส่งต่อ — อยากเลือกเริ่มที่ระดับสูงได้เลย
- **Correct Pattern/Solution:**
  1. `create_issue(..., start_level="room")` — default room
  2. Validate: ถ้า start_level != room → เช็ค `user_level(user) >= start_level` ไม่งั้น 403 (นักเรียนส่งขึ้นสภาไม่ได้)
  3. บันทึก `issue_escalations` (from room → start_level) เป็นประวัติด้วย + status_history note "ผู้แจ้งเลือกเริ่มต้นที่ระดับนี้โดยตรง"
  4. frontend: `selectableLevels` (ตั้งแต่ room ถึงระดับตัวเอง) โชว์เฉพาะผู้มีระดับสูงกว่า student
- **Date Added:** 2026-08-08

### 🛠️ รหัสผ่านเริ่มต้น = เลขรหัสนักเรียน (ไม่ใช่ 1234 เหมือนกัน)
- **Context/Problem:** ต้องการให้รหัสเริ่มต้นต่างกันต่อคน = เลขรหัสนักเรียน; หน้า import เดิมมีช่อง "รหัสผ่านเริ่มต้น" ให้กรอก
- **Correct Pattern/Solution:**
  1. import Excel + seed: `initial_password = student_id` (แล้ว hash) — ถ้า default_password ถูก override (ไม่ใช่ 1234) ค่อยใช้ค่านั้น
  2. ลบช่อง "รหัสผ่านเริ่มต้น" ใน UI (ไม่จำเป็น) — hint บอก "รหัสผ่านเริ่มต้น = เลขรหัสนักเรียน"
  3. มี `POST /api/auth/change-password` (ตรวจ old password ด้วย bcrypt verify) ให้เปลี่ยนได้ที่หน้าโปรไฟล์
- **Date Added:** 2026-08-08

### 🛠️ สถานะ `cancelled` — ผู้แจ้งยกเลิกเรื่องได้ (กันส่งผิด)
- **Context/Problem:** ต้องการให้ผู้แจ้งยกเลิกเรื่องที่ส่งผิด/ไม่ต้องการได้
- **Correct Pattern/Solution:**
  1. `cancel_issue(pool, user_id, issue_id, reason)` — ต้องเป็น reporter_id หรือ admin; ถ้า status=resolved ยกเลิกไม่ได้; set status='cancelled' + insert status_history
  2. frontend: `IssueStatus` union ต้องเพิ่ม `'cancelled'` (ไม่งั้น TS `this comparison appears unintentional`) + `STATUS_LABELS` + statusColor
  3. หน้า "เรื่องที่รับ" default filter = "ยังไม่เสร็จ" (ตัด resolved+cancelled) — ใช้ status='not_resolved' pseudo-value แล้ว filter ฝั่ง client
- **Date Added:** 2026-08-08

### 🛠️ MyProfile — GET/PATCH `/students/me/profile` + user/student/room join
- **Context/Problem:** หน้าโปรไฟล์ต้องดู+แก้ไขข้อมูลตัวเอง (prefix/ชื่อ/นามสกุล/ชื่อเล่น/เบอร์/email)
- **Correct Pattern/Solution:**
  1. `get_my_profile`: join students + users + rooms ตาม user_id (LIMIT 1 กันหลายห้อง)
  2. `update_my_profile`: แก้ students (ชื่อ/prefix/nickname) + users (full_name/phone/email) — dynamic SET เฉพาะ field ที่ส่ง; อัปเดต full_name ใหม่ตอนชื่อเปลี่ยน
  3. หลังแก้เสร็จต้อง `authStore.loadMe()` เพื่อ refresh display name ใน sidebar
- **Date Added:** 2026-08-08

### 🛠️ Frontend theme แดง — sed แทนที่สี + แยก semantic สี
- **Context/Problem:** เปลี่ยน theme น้ำเงิน → แดง (โลโก้โรงเรียนแดง); ใช้ sed `s/blue-N/red-N/g` แต่มันทับสีสถานะ (in_progress/escalated กลายเป็นแดงหมด)
- **Correct Pattern/Solution:**
  1. sed แทนที่สีหลักก่อน (blue→red, indigo→rose) — เร็ว แต่ระวังทับ semantic
  2. แล้วแก้ semantic กลับด้วยมือ: `in_progress`=blue, `escalated`=orange, `resolved`=green, `cancelled`=gray; ระดับ: room=emerald, level=amber, council=rose
  3. หลักการ: **สีแบรนด์ (ปุ่ม/head/brand) ใช้ red, สีสถานะแยก semantic** — อย่าให้ปุ่มกับ badge สีเดียวกันหมด
- **Date Added:** 2026-08-08

### 🛠️ Vue Router Transition — ครอบเฉพาะ content ไม่ใช่ทั้ง layout
- **Context/Problem:** animation "บัคๆ" ไม่เห็น fade — ตอนแรกครอบ `<Transition mode="out-in">` ทั้ง `<RouterView />` ใน App.vue → sidebar กระตุก + หน้าเก่าหายก่อนใหม่มา
- **Correct Pattern/Solution:**
  1. App.vue: `<RouterView />` ตรงๆ (เป็นแค่ shell) — อย่าใส่ transition ที่ครอบทั้ง layout
  2. MainLayout: ครอบ `<RouterView v-slot="{ Component }">` ด้วย `<Transition name="page" mode="out-in" appear>` + `<component :key="route.fullPath">` — animate เฉพาะ content, sidebar นิ่ง
  3. CSS: `.page-enter-active { transition: opacity .35s cubic-bezier(.4,0,.2,1), transform .35s }`, `.page-enter-from { opacity:0; transform: translateY(20px) }` — `mode="out-in"` ต้องให้ enter ช้า/leave เร็ว ไม่งั้นรู้สึกหน่วง
  4. `appear` ให้ animate ครั้งแรก (login→หน้าแรก) ด้วย; list ใช้ `<TransitionGroup name="list">`
- **Date Added:** 2026-08-08

### 🛠️ Pytest integration — pattern test_db_url + client ชี้ settings
- **Context/Problem:** ตอนแรก conftest ใช้ `db_pool` session-scoped → event loop mismatch (`Task attached to a different loop`) ตอน async fixtures
- **Correct Pattern/Solution:**
  1. `test_db_url` (session): สร้าง DB สุ่มชื่อ (`test_db_{uuid}`) ผ่าน sys db → `init_db` → yield URL → drop ตอนจบ
  2. `client` (function): เปลี่ยน `settings.DATABASE_URL = test_db_url` ก่อน `with TestClient(app)` แล้วคืนค่า — pydantic-settings v2 assign field ได้
  3. `clean_database` (function autouse): TRUNCATE master tables CASCADE
  4. test functions เป็น `async def` + `@pytest.mark.asyncio` ใช้ fixtures — อย่าใช้ `run_until_complete` กับ sync client ปนกัน
- **Date Added:** 2026-08-08

### 🛠️ Docker test port ชน — ใช้ port ที่ไม่ซ้ำกัน
- **Context/Problem:** `docker-compose.test.yml` ใช้ host port 5433 → ชนกับ `classroom_test_postgres` ของโปรเจคอื่น (Bind for port already allocated)
- **Correct Pattern/Solution:** ใช้ port เฉพาะโปรเจค (5435) + conftest `DATABASE_URL` ชี้ port นั้น; ถ้ารันหลายโปรเจคบนเครื่องเดียว ตรวจ `docker ps` ก่อนเลือก port
- **Date Added:** 2026-08-08

### 🛠️ Migration file — placeholder หมายเลขต้องเลื่อนตาม parameter ที่มาก่อน
- **Context/Problem:** migration 001 (รื้อหมวดหมู่) พังตอนรัน: `InterfaceError: the server expects 5 arguments for this query, 6 were passed` — query มี `$1` (main_category) แล้วใช้ `NOT IN ($1,$2,$3...)` ที่เริ่มหมายเลข `$1` ใหม่ → ซ้ำกับ parameter ตัวแรก + count เกิน
- **Root Cause:** สร้าง placeholder ของ dynamic list ด้วย `f"${i+1}"` โดยไม่นับ parameter ที่ถูก `$1` จองไว้ก่อนหน้าใน query เดียวกัน
- **Correct Pattern/Solution:** เมื่อ query มี parameter มาก่อนแล้ว (เช่น `$1`), placeholder ของ dynamic list ต้องเริ่มที่ `$2` → `f"${i+2}"`; ตรวจเสมอว่า `sql.count('$') == len(params)` ก่อนรัน (บทเรียนเดียวกับ IndeterminateDatatypeError)
- **Date Added:** 2026-08-16

### 🛠️ Role school-wide (admin/ครูสภา) — room_id = NULL ต้องใช้ LEFT JOIN + user_level คืน council
- **Context/Problem:** ครูสภา/แอดมิน ไม่ผูกห้อง (room_id NULL) → (1) `get_user_roles` ใช้ INNER JOIN rooms → role หายจาก login (ไม่มีห้อง); (2) `user_level` ให้ `ROLE_LEVEL.get("teacher_council", "student")` = "student" → มองเห็นแค่เรื่องตัวเองใน list ทั้งที่ต้องเห็นทุกเรื่อง
- **Root Cause:** สมมติว่าทุกคนต้องมีห้อง; role ใหม่ (teacher_council/admin) เป็น school-wide ไม่มี room → join ทิ้ง row + ระดับกลายเป็น student
- **Correct Pattern/Solution:**
  1. `get_user_roles`: เปลี่ยน JOIN rooms → **LEFT JOIN** + `AND (r.id IS NULL OR r.deleted_at IS NULL)` — คนไม่มีห้องยังได้ role
  2. `user_level`: เช็ค `roles` ที่เป็น `admin/teacher_council/council_president` → คืน `"council"` ก่อน (ไม่เข้า ROLE_LEVEL lookup)
  3. Import Excel: admin/ครูสภา = `school_wide = class_role in ("admin","teacher_council")` → room_id=NULL, ครูทั่วไป = staff_level จากระดับชั้นห้อง
  4. `get_access_scope` (core/rbac): scope 'all' สำหรับ is_admin/teacher_council/admin/council_president, scope 'level' สำหรับ teacher (มี staff_level)
- **Date Added:** 2026-08-16

### 🛠️ ครูทั่วไป (teacher) — scope ระดับชั้นแยกจาก permission check
- **Context/Problem:** ครูทั่วไปมี MANAGE_STUDENTS/VIEW_DASHBOARD เหมือน admin (ตาม roles.json) → ต้องเห็น/จัดการได้แค่ระดับชั้นตัวเอง (ครู ม.4 ดูแลแค่ ม.4) แต่การเช็ค permission อย่างเดียวไม่พอ
- **Correct Pattern/Solution:**
  1. `staff_level` (เช่น 'ม.4') บน students — ครูทั่วไปมี, ครูสภา/แอดมินเป็น NULL
  2. แยก 2 ชั้น: `require_permission_anywhere` (มีสิทธิ์ไหม) → `get_access_scope` / `_teacher_scope` (ขอบเขตข้อมูลระดับไหน) — router ผ่าน `level`/`allowed_level` ไป service
  3. `issue_service`: `_teacher_scope` → `_level_room_ids` → list/get/accept จำกัด room level; `_can_manage_issue` ให้ครูระดับชั้นเรื่องจัดการเรื่องได้แม้ไม่ใช่ผู้รับ
  4. `dashboard_service`: ใส่ `level_where = " AND r.level = $1"` ทุก query (JOIN rooms) เมื่อ scope = level
  5. test: สร้างเรื่อง ม.4 + ม.5 → ครู ม.4 เห็น/รับเรื่อง ม.4 ได้, ม.5 ต้อง 403; ครูสภา/แอดมินเห็นทั้งสอง
- **Date Added:** 2026-08-16

### 🛠️ Dashboard scope — ครูที่ยังไม่มี staff_level ต้องเป็น scope 'none' ไม่ใช่ 'pyramid'→'all'
- **Context/Problem:** `get_access_scope` ตอบ 'pyramid' สำหรับทุกคนที่ไม่ใช่ admin/ครูสภา/ครูที่มีระดับชั้น → dashboard แปลง 'pyramid' เป็น 'all' (ทั้งโรงเรียน) เพื่อให้ council_member ดูได้ แต่ครูที่สมัครโดยไม่ระบุห้อง (`staff_level` NULL — register_user ตั้ง None) ตกเงื่อนไขเดียวกัน → เห็นข้อมูลทั้งโรงเรียนทั้งที่ควรเห็นแค่ระดับชั้นตัวเอง (สิทธิ์สูงเกิน)
- **Root Cause:** scope 'pyramid' ใช้ร่วมกันระหว่าง council_member (ดูได้ทั้งโรงเรียนจริง) กับครูที่ยังไม่ตั้งระดับ (ต้องไม่เห็นเลย) — แยกไม่ออกจาก scope ค่าเดียว
- **Correct Pattern/Solution:**
  1. `get_access_scope`: ถ้า role เป็น teacher แต่ `staff_level` ว่าง → คืน `{"scope": "none"}` (แยกจาก 'pyramid'); เช็คก่อนด้วยว่าไม่มี membership อื่นที่ให้ scope สูงกว่า
  2. `dashboard_service`: `_scope_clause('none')` → `" AND 1 = 0"` (ไม่เห็นเรื่อง); `_count_people` ต้องมี branch `scope == "none"` → (0,0) — อย่าลืม helper ตัวรอง (ตอนแรกคิดว่ามีแค่ 2 branch แล้ว test จับได้ว่าจำนวนนักเรียน/ห้องยังรั่ว)
  3. frontend: รองรับ `scope === 'none'` แสดง banner "ยังไม่ได้กำหนดระดับชั้น" แทน "ภาพรวมทั้งโรงเรียน"
- **Date Added:** 2026-08-16

### 🛠️ Deep-DB verify ใน test — ห้าม copy query service ตรงๆ + ต้องสร้าง scenario ที่ทำให้ rule มองเห็นได้
- **Context/Problem:** test overdue ตรวจ DB ด้วย query ที่ copy จาก service แทบทั้งดุ้น (`cd.id = (SELECT MAX(id)...)`) → regression ที่ลบเงื่อนไข "latest countdown เท่านั้น" ออก (นับ countdown ไหนก็ได้ที่เกิน) จะยังผ่านเพราะทุกเรื่องมี countdown แค่ 1 แถว
- **Root Cause:** ตรวจ "ด้วยวิธีเดียวกัน" ไม่ใช่ "ตรวจอิสระ" + ไม่มีข้อมูลที่แยกความต่างของกฎออกมา
- **Correct Pattern/Solution:**
  1. เขียนการตรวจอิสระด้วยรูปแบบที่ต่างกัน เช่น service ใช้ `EXISTS + MAX(id)` → test ใช้ correlated `(SELECT deadline FROM issue_countdowns ... ORDER BY id DESC LIMIT 1) < NOW()`
  2. สร้าง scenario ที่ทำให้กฎ "มองเห็นได้": ให้เรื่องหนึ่งมี countdown 2 แถว — อันเก่าเลยกำหนด + อันใหม่ยังไม่เกิน (ยืดเวลา) → ต้อง NOT overdue; ถ้า implementation นับ "มี countdown ไหนเกินก็ได้" เรื่องนี้จะติดเป็น overdue ให้ test จับได้
  3. trend อย่า assert `trend[-1]['count'] == N` (ข้ามเที่ยงคืน Asia/Bangkok แล้ว flaky — เรื่องที่สร้างก่อนเที่ยงคืนตกไปอยู่วันก่อน) → ใช้ `sum(t['count'] for t in trend) == N`
- **Date Added:** 2026-08-16

### 🛠️ Dashboard หลาย query รวมหมวดเดียว — ตัวเลขระดับบนต้องรวมจาก key set เดียวกับหมวดย่อย
- **Context/Problem:** `total_issues`/`pending/...` คำนวณจาก `by_status_all` ที่รวมทุก row ที่ query คืนมา แต่ `main_categories[].total` + `recent_issues` + `top_subcategories` รวมจากเฉพาะ `category_codes` ใน config → ถ้ามี row ที่ `main_category` อยู่นอก config (หมวดเก่าที่ถูกลบ, ตัด space ผิด, insert ตรง) ตัวเลข top-level กับรายหมวดไม่ตรงกัน (sum ของ pending+... != total)
- **Correct Pattern/Solution:** สร้าง aggregate ทั้งหมดจาก key set เดียวกัน — `total_by_main` และ `by_status_all` ต้อง loop เฉพาะ `category_codes` (`by_main_status.get(mc, {})`) เหมือนกับที่หมวดย่อย/เรื่องล่าสุดทำ; หรือเพิ่ม CHECK constraint ที่ `issues.main_category`
- **Date Added:** 2026-08-16
