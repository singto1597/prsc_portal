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

### 🛠️ `str(None)` ใน Python = `"None"` (truthy!) — ตอนแปลงค่าเซลล์ว่างจาก Excel ต้อง `or ""` เสมอ
- **Context/Problem:** `student_id = str(_get(row, idx, "รหัสนักเรียน")).strip()` — ถ้าเซลล์ว่าง `_get` คืน `None` → `str(None)` = `"None"` ซึ่ง truthy → `if not student_id` ไม่เด้ง → import แถวที่ไม่มีรหัสนักเรียนเข้าไปเป็น user ชื่อ "None" (test จับได้: imported=3 ทั้งที่ควรเป็น 2)
- **Root Cause:** ลืมว่า `str(None)` ไม่ได้คืน string ว่าง; pattern `str(x or "")` ใช้กันในไฟล์เดียวกัน (first_name/nickname) แต่ 2 จุด (student_id, room_code) ใช้ `str(x)` ตรงๆ
- **Correct Pattern/Solution:** ใช้ `str(_get(...) or "").strip()` ทุกจุดที่แปลงค่าที่อาจเป็น `None`; และ error ต่อ row ต้องมีชื่อคอลัมน์ (เช่น "เลขที่ต้องเป็นตัวเลข (ได้ค่า: 'abc')") — ไม่ใช่แค่ `ข้อมูลผิดรูปแบบ/ซ้ำ (...)` ที่ไม่บอกว่า field ไหน
- **Date Added:** 2026-08-16

### 🛠️ asyncpg คืน `jsonb` เป็น **string** — ต้อง `json.loads` ก่อน `list()`
- **Context/Problem:** response ของ `GET /import-jobs` โชว์ `"error_logs":["[","]"]` — `error_logs` เป็นคอลัมน์ `JSONB NOT NULL DEFAULT '[]'::jsonb` แต่ asyncpg คืนค่าเป็น string `"[]"` (ไม่ใช่ list) → `list("[]")` แยกเป็น `['[', ']']`
- **Root Cause:** asyncpg ไม่ parse `jsonb` เป็น Python object ให้อัตโนมัติ (ต้องลง codec เอง); test ที่อ่านเองใช้ `json.loads(job["error_logs"])` เป็นสัญญาณว่า column นี้คืน string
- **Correct Pattern/Solution:** เมื่อจะ `list()` ค่า JSONB ที่ asyncpg คืนมา ให้เช็คก่อน: `if isinstance(raw, str): raw = json.loads(raw)` (wrap try/except → `[]`); แล้วค่อย `list(raw or [])` — ใช้ได้ทั้ง DB จริง (string) และ mock (list)
- **Date Added:** 2026-08-16

### 🛠️ Fixture ที่เรียก `register_user` จะสร้าง user + student row ด้วย — นับ count ต้อง scope ด้วย ID
- **Context/Problem:** test `reimport` assert `users == 1` หลัง import แต่ได้ 2 — `admin_user` fixture เรียก `register_user` ซึ่งสร้างทั้ง user และ student ของ admin → count รวม fixture เข้าไปด้วย
- **Root Cause:** เข้าใจว่า fixture สร้างแค่ "สิทธิ์" แต่จริงๆ สร้าง record จริงในตาราง; test ที่ assert `count(*)` รวม row ของ fixture
- **Correct Pattern/Solution:** assert แบบ scope เฉพาะเป้าหมายเสมอ เช่น `SELECT count(*) FROM users WHERE username = '47001'` / `WHERE student_id IN (...)`, หรือ `JOIN rooms` ให้กรอง row ที่ `room_id IS NULL` ออก (กรณี fixture ระดับโรงเรียน); ระวัง `VARCHAR(10)` ของ `students.student_id` ด้วย — `f"ID{username}"` เกิน 10 ตัว → `StringDataRightTruncationError`
- **Date Added:** 2026-08-16

### 🛠️ Frontend `as` cast — inline `(await api.get()) as X` ผ่าน type-check แต่ `const res = await ...; res as X` เด้ง TS2352
- **Context/Problem:** `npm run type-check` ฟ้อง `TS2352: Conversion of type 'AxiosResponse<...>' to type 'Room[]'` เฉพาะที่เขียน `const res = await api.get(...); return res as Room[]` — แต่ `issue.ts` ที่เขียน `(await api.get(...)) as Issue[]` inline ผ่าน และ test probe (inline) ก็ผ่าน
- **Root Cause:** `services/api.ts` เป็น axios instance ธรรมดา (type ยังเป็น `Promise<AxiosResponse>`) มี interceptor ปลด `response.data` ตอน runtime เท่านั้น; TS เปรียบเทียบ `AxiosResponse` กับ array type ต่างกันตามตำแหน่งการ cast (empirical — โปรเจคนี้ inline cast ผ่านเสมอ)
- **Correct Pattern/Solution:** cast inline ทันทีใน expression: `return (await api.get('/api/rooms')) as Room[];` — อย่า assign ตัวแปรคั่นก่อน cast; `as unknown as X` ก็ใช้ได้เสมอแต่ไม่สวย; ถ้าสงสัยว่าไฟล์อื่นพังไหมให้รัน `npx vue-tsc --noEmit -p tsconfig.app.json` (--build มี incremental cache — ลบ `node_modules/.tmp/tsconfig.app.tsbuildinfo` ก่อนถ้าต้องการ ground truth)
- **Date Added:** 2026-08-16

### 🛠️ ARQ + asyncpg — สถานะ QUEUED อย่า allow restart (กันยิงคิวซ้ำ) + ฝาก recovery ไว้ที่ worker startup
- **Context/Problem:** `RESTARTABLE_STATUS` เริ่มแรกมี QUEUED → กด "เริ่มงาน" 2 ครั้งบน job QUEUED ได้ 200 (enqueue ซ้ำ) — test `start twice → 409` จับได้
- **Root Cause:** ตั้งใจให้ restart ได้กรณี Redis หาย แต่เผลอเปิดช่อง double-enqueue race (worker อาจ claim ไปแล้ว)
- **Correct Pattern/Solution:** `RESTARTABLE_STATUS = {PENDING, FAILED}` เท่านั้น; กรณี job ค้างใน QUEUED ที่ Redis หาย ให้ `recover_stuck_jobs` (worker startup) ครอบ `status IN ('PROCESSING','QUEUED')` + `updated_at < NOW() - INTERVAL '35 minutes'` → reset QUEUED + re-enqueue; claim idempotent ด้วย `FOR UPDATE` + status check ทำให้ re-enqueue ซ้ำปลอดภัย
- **Date Added:** 2026-08-16

### 🛡️ Privilege escalation — อย่าอนุมานสิทธิ์จากค่าใน Excel ที่ uploader ส่งมา
- **Context/Problem:** worker นำเข้านักเรียนจาก Excel กำหนด `school_wide = class_role in ("admin", "teacher_council")` จาก cell "ตำแหน่งในห้องเรียน" ที่ uploader เขียนเอง → ครูระดับชั้น (allowed_level='ม.4') ส่งแถวที่มีตำแหน่ง "แอดมิน"/"ประธานสภา" → worker สร้างบัญชี is_admin=true ที่ควบคุมทั้งโรงเรียนได้ (privilege escalation) — review พบเป็น HIGH
- **Root Cause:** scope ของ uploader (มาจาก DB: `get_access_scope`) กับ role ในแถว Excel (มาจาก input ที่ปลอมแปลงได้) ถูกผสมกัน — ใช้ค่าที่ผู้ใช้ควบคุมเป็นตัวให้สิทธิ์
- **Correct Pattern/Solution:** สิทธิ์ต้องมาจากผู้ควบคุมข้อมูลเสมอ: (1) Router ตรวจ `scope == 'none'` → 403 (ครูที่ยังไม่มีระดับชั้น "นำเข้าทั้งโรงเรียน"); (2) `default_password` รับเฉพาะ `{"", "1234"}` เท่านั้น; (3) ใน `_process_single_row` ถ้า `allowed_level is not None` (uploader ระดับชั้น) → ปฏิเสธ role ใน `SCHOOL_WIDE_ROLES = {"admin","teacher_council","council_president","council_member"}`; สรุปง่าย: **allowed_level is None ⟺ uploader เป็น school-wide** (หลัง reject scope='none') — ใช้ค่าจาก DB ไม่ใช่จากไฟล์
- **Date Added:** 2026-08-17

### 🛠️ Batch insert พังกลางคัน (rollback) — snapshot ตัวนับก่อนลอง + เคลียร์ cache ที่มี phantom ID
- **Context/Problem:** worker ทยอย insert เป็น batch (1 transaction/chunk) แต่มี fallback ทีละแถวเมื่อ `asyncpg.PostgresError` → ตัวนับ `imported/skipped/errors` เพิ่มใน try ก่อน transaction commit → เมื่อ batch rollback ตัวนับยังค้าง (นับซ้ำ: imported=3 ทั้งที่จริง 2) + `ctx.room_cache`/`user_cache` เก็บ room/user id ที่ rollback ไปแล้ว (phantom ID) → fallback + batch ถัดไป insert ผิดที่ — review พบเป็น HIGH (double-count)
- **Root Cause:** ตัวนับเป็น side-effect ระหว่าง transaction ไม่ใช่ผลหลัง commit; cache ไม่รู้ว่า transaction ล้ม
- **Correct Pattern/Solution:** ก่อน `try` ให้ `snapshot = (imported, skipped, len(errors))` → ใน `except PostgresError` คืนค่า snapshot (คืน `imported, skipped` + `del errors[snapshot_len:]`) + `ctx.room_cache.clear()`/`ctx.user_cache.clear()` → แล้วค่อย fallback ทีละแถว; test จับได้โดยส่งแถวที่ทำให้ batch พัง (เช่น `room_code` ยาวเกิน VARCHAR(10) → `StringDataRightTruncationError`) แทรกกลาง chunk แล้ว assert imported ไม่นับซ้ำ
- **Date Added:** 2026-08-17

### 🛠️ Upsert student ให้ atomic ด้วย `ON CONFLICT` — แต่ partial unique index ไม่ชน NULL
- **Context/Problem:** SELECT-แล้ว-INSERT/UPDATE student ไม่อะตอมิก (2 งานชนกันสร้างแถวซ้ำ) → review แนะนำ partial unique index `(room_id, student_id) WHERE deleted_at IS NULL` + `INSERT ... ON CONFLICT (room_id, student_id) WHERE deleted_at IS NULL DO UPDATE` — แต่ Postgres **unique index ไม่ถือว่า NULL เท่ากัน** → แถว school-wide (room_id NULL) จะไม่ conflict และ reimport สร้างซ้ำ
- **Root Cause:** partial unique index บนคอลัมน์ที่อาจเป็น NULL → NULL แต่ละค่าเป็น "ต่างกัน" ในดัชนี
- **Correct Pattern/Solution:** แยก 2 กรณีใน `_process_single_row`: ถ้า `room_id is not None` → `ON CONFLICT ... DO UPDATE`; ถ้า `room_id IS NULL` (school-wide) → คง SELECT-แล้ว-INSERT/UPDATE เดิม (หรือใช้ index แบบ `NULLS NOT DISTINCT` ถ้า PG15+ — แต่กรณีนี้แยก path ง่ายกว่า); เพิ่ม index ใน `init_db` + migration 003 (idempotent: `CREATE UNIQUE INDEX IF NOT EXISTS`); test: reimport แอดมิน (room NULL) 2 รอบ → user/student ต้อง 1 ตัว
- **Date Added:** 2026-08-17

### 🛠️ Scope filter ตอน list/start — อย่าโชว์/เริ่มงานของคนอื่นให้ครูระดับชั้น
- **Context/Problem:** `GET /import-jobs` และ `POST /start-import-job` ตรวจแค่ MANAGE_STUDENTS ไม่กรองตาม access scope → ครู ม.4 เห็นงาน import ทั้งโรงเรียนของแอดมิน และ start งานที่ไม่ได้เป็นระดับตัวเองได้
- **Root Cause:** service รับแค่ `limit`/`job_id` ไม่รู้ scope ของผู้เรียก
- **Correct Pattern/Solution:** Router เรียก `get_access_scope` แล้วส่ง `access_scope`/`access_level` ไปให้ service: list → `WHERE allowed_level = $2` (level), `[]` (none); start → `ForbiddenError` ถ้า `scope=='none'` หรือ `job["allowed_level"] != access_level`; กฎทุกเลเยอร์: **สิทธิ์ของ user มาจาก DB (`get_access_scope`) ไม่ใช่จาก payload**
- **Date Added:** 2026-08-17
