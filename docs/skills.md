# 🏫 PIRIvoice — Lessons จากพัฒนาระบบรับฟังความคิดเห็นและปัญหา

> ส่วนนี้บันทึกบทเรียนที่เจอจริงระหว่างพัฒนาระบบ PIRIvoice (สภานักเรียน) ตั้งแต่โครงสร้าง → backend → frontend → deploy

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

### 🛡️ Template ที่มีแถวตัวอย่าง = ช่องสร้าง account จริง — ต้อง guard ที่ชั้น import ไม่ใช่แค่เตือนในข้อความ
- **Context/Problem:** `build_template_xlsx_bytes` ใส่แถวตัวอย่าง (00001, 00002) ลง Sheet ข้อมูล — ครูดาวน์โหลด Template แล้วอัปโหลดทั้งไฟล์ (ไม่ลบแถวตัวอย่าง) → worker สร้าง user/student จริง + room อัตโนมัติ (ม.4/1, ม.4/2) โดย password เดาได้ = เลขรหัส (00001/00001) — review ยืนยันว่าถึงได้ (MEDIUM)
- **Root Cause:** `_process_single_row` ตรวจแค่ `student_id` ไม่ว่าง → แถว placeholder ผ่าน validation ทั้งหมด; ข้อความเตือน "ลบออกก่อนอัปโหลด" ไม่มีผลบังคับ
- **Correct Pattern/Solution:** กันที่ชั้น import: `_process_single_row` ปฏิเสธแถวที่ `student_id.startswith("000")` (คืน per-row error "รหัสขึ้นต้น 000 = แถวตัวอย่าง") — ครอบคลุมทั้ง Template ที่ดาวน์โหลดและไฟล์ที่เขียนมือ; ข้อความใน UI/คำแนะนำให้บอกว่า "ระบบข้ามแถว 000xx อัตโนมัติ" (ไม่ใช่แค่เตือนให้ลบ); **กฎ: สิ่งที่อยู่ในไฟล์ตัวอย่างต้อง import ผ่านไม่ได้เสมอ (defense in depth — อย่าพึ่งคำเตือน)**
- **Date Added:** 2026-08-17

### 🛡️ SweetAlert2 `html` = innerHTML — user data ต้อง escape (self-XSS)
- **Context/Problem:** `Swal.fire({ html: `ไฟล์ <b>${job.file_name}</b> ...` })` — `file_name` เป็นชื่อไฟล์จาก user ที่ backend สะท้อนกลับ verbatim (ไม่ sanitize) → ไฟล์ชื่อ `<img src=x onerror=...>.xlsx` (ถูกกฎหมายใน Linux/Mac) รัน script ตอนโชว์ dialog — review ยืนยัน (LOW, self-XSS เฉพาะคนอัปโหลด)
- **Root Cause:** SweetAlert2 แทรก `html` ผ่าน innerHTML/DOMParser โดยไม่ escape; Vue `{{ }}` escape เอง แต่ `html:` option ไม่
- **Correct Pattern/Solution:** มี helper `escapeHtml(value)` (replace `& < > " '`) ใช้ทุกจุดที่แทรก user data ลง `html:`; ถ้าไม่ต้องใช้ layout → ใช้ `text:` (Swal escape ให้); ใช้ `?? c` คืนค่าเดิมเมื่อ Record lookup ไม่เจอ — **กฎ: user input ทุกค่าที่เข้าออก backend (ชื่อไฟล์, ชื่อนักเรียน...) อย่า interpolate ลง html โดยไม่ escape**
- **Date Added:** 2026-08-17

### 🛠️ `URL.revokeObjectURL` หลัง `link.click()` ทันที — race กับ download async ของ browser
- **Context/Problem:** `handleDownloadTemplate` สร้าง blob URL → `link.click()` → revoke ทันที — browser ดาวน์โหลดแบบ async ถ้า revoke ก่อนจับ reference จะได้ไฟล์ 0 bytes/aborted (Firefox documented bug 1810828; FileSaver.js เลื่อน revoke ~40s) — review พบ
- **Root Cause:** revoke หลัง click ยังเร็วเกิน — `click()` เป็นแค่ "เริ่มต้น" กระบวนการดาวน์โหลด
- **Correct Pattern/Solution:** revoke แบบ defer: `setTimeout(() => URL.revokeObjectURL(url), 1000)` (คลิกยังอยู่ใน user gesture ทันที, revoke ทีหลัง); ถ้าต้องการชัวร์ ตรวจ `blob.size` ก่อนสร้าง URL — **กฎ: revoke blob URL ต้องหน่วงเสมอ ถ้าใช้แล้วทิ้ง**
- **Date Added:** 2026-08-17

### 🛠️ Legacy `.xls` (BIFF/OLE) — openpyxl อ่านไม่ได้ ต้องจำกัด `.xlsx` ทั้ง frontend + backend
- **Context/Problem:** UI ยอมรับ `.xls` (`accept=".xlsx,.xls"`, regex `\.(xlsx|xls)$`) → user เลือกไฟล์ .xls จริง ผ่าน gate → backend `endswith((".xlsx",".xls"))` ผ่าน → `openpyxl.load_workbook` อ่าน BIFF ไม่ได้ → 400 "อ่านไฟล์ Excel ไม่สำเร็จ" ทั้งที่ UI โฆษณาว่ารองรับ — review พบ
- **Root Cause:** เปิดช่อง `.xls` ไว้หลายจุด (frontend regex + accept + backend router) แต่ parser รองรับแค่ OOXML zip (.xlsx/.xlsm)
- **Correct Pattern/Solution:** จำกัด `.xlsx` อย่างเดียวทุกจุดที่จับ ext: regex `/\.xlsx$/i`, `accept=".xlsx"`, backend `endswith(".xlsx")` — **กฎ: อย่าให้ UI โฆษณารูปแบบที่ pipeline อ่านไม่ได้; เช็ค ext เป็นแนวเดียวกันทุกเลเยอร์**
- **Date Added:** 2026-08-17

### 🛠️ Short-polling กลืน error — progress bar ค้างเงียบ + empty state หลอก ต้องมี loadError + กัน poll วน
- **Context/Problem:** poll interval มี `catch {}` ว่าง → network หลุด: bar ค้างที่ 60% ไม่มีข้อความ (runningJobs ยังไม่ว่าง → poll วนไม่มีวันหยุด); `refreshJobs` ก่อนหน้ากลืน error → โชว์ "ยังไม่มีไฟล์ในคิว" ทั้งที่มีไฟล์จริง (ครูเห็นแล้วอัปโหลดซ้ำ = duplicate job) — review ยืนยัน (MEDIUM)
- **Root Cause:** ทุก catch เงียบ ไม่แยก "ไม่มีข้อมูล" กับ "อ่านข้อมูลไม่ได้"; ไม่นับความล้มเหลวต่อเนื่องของ poll
- **Correct Pattern/Solution:**
  1. แยก state: `loadError` (refresh/โหลดครั้งแรกพลาด) vs `isPollError` (poll ติดกันเกิน `POLL_FAIL_LIMIT=3`)
  2. `refreshJobs` สำเร็จ → เคลียร์ error + `pollFailStreak=0`; ไม่มีงานวิ่ง → `stopPolling()`; พลาด → `loadError=true` (เก็บรายการเดิมไว้ ไม่ลบ)
  3. `pollOnce()` แยกเป็น function — สำเร็จ reset streak; พลาด `streak++` แล้ว `isPollError=true` ถ้าเกินลิมิต (**ไม่หยุด poll** — พอ network กลับมา update เอง, แบนเนอร์หายเอง)
  4. Template: `v-else-if="loadError"` → error panel + ปุ่ม "ลองใหม่" (แทน empty state); empty state ต้องโชว์เฉพาะเมื่อ fetch สำเร็จจริงๆ
  - **กฎ: UI ที่มี state "ว่าง" ต้องแยกจาก state "อ่านไม่ได้" เสมอ; loop poll ต้องมีใน-flight guard + นับ failure**
- **Date Added:** 2026-08-17

### 🛠️ เซลล์ Excel ที่เป็นตัวเลข float (40000.0) — `str()` ได้ "40000.0" ต้องตัด `.0` ก่อนใช้เป็น identifier
- **Context/Problem:** import นักเรียนได้ `student_id = "40000.0"` (login ได้ด้วย 40000.0/40000.0) — ไฟล์ .xlsx ที่สร้างจากเครื่องมืออื่น (Excel/Google Sheets/macro) เก็บเลขรหัสเป็น `<v>40000.0</v>` ใน XML → `openpyxl._cast_number` (worksheet/_reader.py) เห็น `.`/`e` → คืน `float` (40000.0) → `str(40000.0)` = `"40000.0"`
- **Root Cause:** เขียน `str(cell or "").strip()` ตรงๆ — ไม่ได้คิดว่า cell เป็น float ที่ลงตัว; (openpyxl เขียน float 40000.0 เองจะ normalize เป็น int ตอน save → `make_xlsx_bytes` ปกติไม่เจอ bug นี้ ต้อง craft XML ให้เก็บ `<v>40000.0</v>` ถึงจะจำลองได้)
- **Correct Pattern/Solution:**
  1. helper `_cell_to_str(value)`: `None → ""`, `float ที่ is_integer() → str(int(value))`, นอกนั้น `str(value).strip()` — ใช้กับ `student_id`/`room_code` (identifier) แทน `str(x or "")`
  2. float ที่มีเศษ (40000.5) อย่า truncate — คืน `str(40000.5)` ตามเดิม (ข้อมูลผิด ปล่อยให้เห็นไม่ใช่ตัดทิ้งเงียบๆ)
  3. test: สร้าง xlsx แล้ว `zipfile` เข้าไปแก้ XML sheet — regex `(<c r="A\d+"...>)(<v>)(\d+)(</v>) → \1\2\3.0\4` เฉพาะคอลัมน์ A (อย่าแทน `<v>` ทั้งหมด — จะพัง shared-string index ของคอลัมน์ string); assert student_id == '40000' + login ผ่าน 40000/40000
  - **กฎ: ค่า identifier ที่อ่านจาก spreadsheet ต้องแปลงผ่าน "cell → string" ที่จัดการ float ลงตัวเสมอ; อย่า `str()` ตรงๆ**
- **Date Added:** 2026-08-17

### 🛠️ init_db ต้องรัน migrations ก่อนสร้าง index — ไม่งั้น DB เก่า crash-loop ตั้งแต่ startup
- **Context/Problem:** staging crash-loop ทุก replica ด้วย `UndefinedColumnError: column "main_category" does not exist` (init_db.py) — deploy schema ใหม่ (รื้อหมวดหมู่ → migration 001 เพิ่ม `issues.main_category`) ลงบน DB เดิม
- **Root Cause:** `init_db` สร้าง table + **index ทั้งหมดใน transaction เดียว** (รวม `idx_issues_main_category ON issues(main_category)`) แล้วค่อยรัน `run_migrations` ทีหลัง → DB เก่าที่ยังไม่มีคอลัมน์ crash ตอน `CREATE INDEX` ก่อน migration จะมีโอกาสเพิ่มคอลัมน์; symptom ที่น่ากลัวคือ API ทุกตัว "Not found" เพราะ backend เริ่มไม่ติด (ถึงมี route ก็รับไม่ได้)
- **Correct Pattern/Solution:** ลำดับใน init_db = `CREATE TABLE IF NOT EXISTS` → `run_migrations` → สร้าง index ที่อ้างคอลัมน์ (แยก index ออกเป็น block หลัง migrations); migration ทุกตัวเขียนให้ idempotent (`ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`) จึงรันซ้ำบน DB ใหม่ได้ปลอดภัย; **กฎ: คอลัมน์ที่เพิ่มผ่าน migration ต้องมีอยู่ก่อน statement ที่อ้างมัน (index/query) — ตรวจเส้นทาง upgrade DB เดิมด้วยเสมอ ไม่ใช่แค่ fresh install**; test regression: สร้าง DB ทิ้ง → สร้าง `issues` แบบไม่มี `main_category` → รัน `init_db` → assert คอลัมน์ + index ถูกสร้าง
- **Date Added:** 2026-08-17

### 🛠️ Rebrand เปลี่ยนชื่อโปรเจค (PRSC Portal → PIRIvoice) — แยก "ชื่อที่โชว์" กับ "identifier ที่ผูกข้อมูล"
- **Context/Problem:** rebrand โปรเจคครั้งใหญ่ ต้องไล่เปลี่ยนชื่อทุกจุด แต่บางตำแหน่งผูกกับข้อมูลจริง — เปลี่ยนผิดทีเดียว deploy แล้วข้อมูล "หาย" หรือเว็บ CORS พังเงียบๆ
- **Root Cause:** ชื่อเดียวกันซ้ำหลายชั้น (UI string / docs / package name / docker image / volume / DB name / CORS origin) แต่ความเสี่ยงต่างกัน — identifier ที่ persistent (volume ที่ services mount, DB name, domain) ไม่ใช่แค่เครื่องสำอาง
- **Correct Pattern/Solution:**
  1. **เปลี่ยนได้ทันที (ปลอดภัย):** display string ในหน้าเว็บ (index.html title/meta, sidebar, login, FastAPI title/description), docs/comments/docstring, package name (`package.json`+`package-lock.json` ต้องแก้คู่กัน), docker image name (แก้ให้ตรงกันทั้ง `pull_all.sh` + `docker-compose.app.yml` — rollback ยังทำงานเพราะ oh_shit deploy ผ่าน compose), container/DB name ของ test (throwaway), temp prefix
  2. **ผูกกับข้อมูลจริง → ระวัง:** named volume ที่ service mount อยู่ (เปลี่ยนชื่อ = Docker สร้าง volume ใหม่เปล่า ข้อมูลเก่าเหลือเป็น orphan — ถ้าจำเป็นให้ใช้ `external: true` + `name: <ชื่อเดิม>`), DB name ใน .env จริง (ต้อง `ALTER DATABASE` ไม่ใช่แค่แก้ตัวอักษร), CORS origins (โดเมนที่ deploy อยู่ถูกลบ → เว็บเก่าเรียก API ไม่ได้) — rebrand นี้เก็บโดเมนเก่าไว้ช่วงเปลี่ยนผ่าน + เพิ่มโดเมนใหม่ pirivoice.com
  3. **เจอ bug ซ่อนใน infra compose นี้:** services mount `${ENV_NAME}_postgres_data` แต่ `volumes:` section ประกาศ `prsc_staging_*`/`piri_staging_*` (ไม่ได้ถูก mount — dead) → ข้อมูลจริงอยู่ที่ volume ที่ Docker auto-create ชื่อ `staging_postgres_data`/`production_postgres_data` — อย่าเดาว่าข้อมูลอยู่ตามชื่อใน volumes section
  4. **คีย์เวิร์ดค้นหา:** index.html ต้องมี `<meta name="description">` + `<meta name="keywords">` (PIRIvoice / Pirivoice / เสียงจากชาวพิริยาลัย / ระบบรับฟังความคิดเห็นและปัญหา / สภานักเรียน) — และเก็บชื่อเก่าไว้ที่ readme ("เดิมชื่อ PRSC Portal") เพื่อให้ search คำเก่ายังเจอ
- **Date Added:** 2026-08-17

### 🛠️ Seed users (admin/ครูสภา/ประธานสภา) ตอนเปิดระบบครั้งแรก — username ยาว ≠ student_id VARCHAR(10) + bังคับเปลี่ยนรหัสครั้งแรก
- **Context/Problem:** ต้องการสร้างบัญชีผู้ดูแลระบบอัตโนมัติตอน `init_db`/startup ครั้งแรก ด้วย username เดายาก แล้วบังคับเปลี่ยนรหัสตอน login ครั้งแรก — แต่ `students.student_id` เป็น `VARCHAR(10)` (จำกัด 10 ตัว) ขณะที่ `users.username` เป็น `VARCHAR(100)`
- **Root Cause:** เข้าใจผิดว่า username กับ student_id ต้องเป็นค่าเดียวกัน → username ยาวๆ (`piri_admin_9f2k3c` = 17 ตัว) เกิน 10 ตัวของ student_id → INSERT พัง (หรือต้องสั้นจนเดาได้)
- **Correct Pattern/Solution:**
  1. **แยกค่า:** `users.username` (login, VARCHAR 100) = ยาวๆ เดายาก `piri_<role>_<hex6>`; `students.student_id` (identifier, VARCHAR 10) = สั้นๆ แยกกัน เช่น `PADM` + `secrets.token_hex(2).upper()` → แสดงในโปรไฟล์เป็น "รหัสนักเรียน"
  2. **idempotent:** ตรวจก่อน seed ว่า `students.class_role IN ('admin','teacher_council','council_president') AND status='active' AND deleted_at IS NULL` มีแล้วหรือยัง → มีแล้วข้าม (กันสร้างซ้ำตอน restart/test)
  3. **บังคับเปลี่ยนรหัส:** เพิ่มคอลัมน์ `users.must_change_password BOOLEAN DEFAULT FALSE` (migration `ADD COLUMN IF NOT EXISTS` + แก้ `CREATE TABLE` ใน init_db ให้ตรงกัน) → seed ตั้ง TRUE → `change_password` เคลียร์เป็น FALSE → frontend guard redirect ไปหน้าเปลี่ยนรหัส
  4. **Credentials:** เขียนไฟล์ (gitignored) + log ตอน startup; path จาก `settings.SEED_CREDENTIALS_FILE`
  - **กฎ: username (login) กับ student_id (identifier 10 ตัว) ไม่จำเป็นต้องค่าเดียวกัน; ฟีเจอร์ seed/boot ที่ idempotent ต้อง "เช็คมีแล้ว → ข้าม" ไม่ใช่ "INSERT ON CONFLICT" อย่างเดียว** (กรณี role ซ้ำกับ user ต่างกัน)
  - **เทส Gotcha:** `TestClient(app)` เปิด lifespan → seed รันก่อน test body → test ที่เรียก `seed_default_users` เองได้ `{}` (โดน skip) — **อย่าใช้ fixture `client` ใน test seed; สร้าง TestClient เองหลัง seed** (คุมคำสั่ง seed เองได้)
- **Date Added:** 2026-08-18

### 🛠️ Frontend mobile UX — iOS auto-zoom, dropdown โดน overflow-hidden ตัด, ตารางบนจอเล็ก
- **Context/Problem:** ปรับปรุงมือถือเจอ 3 บั๊ก/จุดหักมุม: (1) iOS Safari ซูมจอทุกครั้งที่แตะ input ที่ font < 16px; (2) dropdown เมนูที่วางใน container `overflow-hidden` โดนตัด (render ยาวเกิน parent); (3) ตาราง `<table>` บนจอแคบอ่านไม่รู้เรื่อง
- **Root Cause:** (1) iOS auto-zoom เป็นพฤติกรรมบังคับของช่องกรอกที่ font-size ต่ำกว่า 16px — Tailwind `text-sm` (14px) ตกทุกจุด; (2) CSS overflow clipping ใช้กับ container ที่มี dropdown อยู่ด้านใน; (3) ตารางหลายคอลัมน์ถูกบีบแนวตั้งบนความกว้างแคบ
- **Correct Pattern/Solution:**
  1. **iOS zoom:** ใน `main.css` เพิ่ม `@media (max-width:640px){ input,textarea,select { font-size:16px !important } }` — override `text-sm` เฉพาะมือถือ กัน zoom ทุกครั้งที่แตะ
  2. **Dropdown ถูกตัด:** แยกโครงสร้าง — container ที่ `overflow-hidden` ไว้เฉพาะพื้นหลัง/ลวดลาย (วงกลมตกแต่ง) ส่วนปุ่มเมนู + dropdown ย้ายไปอยู่ใน `<div class="relative">` ครอบนอก (ไม่โดน clip) + จัด z-index (overlay `z-20` ปิดเมนู อยู่ใต้ปุ่มเมนู `z-30`)
  3. **ตารางมือถือ:** dual layout — `md:hidden` = การ์ดรายการ (avatar/ชื่อ/ข้อมูล) + `hidden md:block` = `<table>` เดิมบนเดสก์ท็อป; ฟังก์ชัน action (เช่น เปลี่ยนตำแหน่ง) ใช้ร่วมกันได้
  4. **Filter row:** `grid grid-cols-1 sm:flex sm:flex-wrap` + select `w-full sm:w-auto` → บนมือถือเรียงแนวตั้งเต็มแถว ไม่เบียดกัน
  5. **ชื่อ/ข้อความล้น:** เติม `min-w-0` + `break-words` ที่ element ใน flex/grid (ชื่อคน, หัวข้อ) — กัน flex ตัดหรือกว้างเกินจอ
- **Date Added:** 2026-08-18

### 🛠️ Docker Swarm deploy — top-level volume key ใส่ `${ENV_NAME}` ไม่ได้ + `docker stack deploy` ไม่อ่าน `.env` เอง
- **Context/Problem:** เขียนสคริปต์ตั้งค่าระบบ (setup.sh) ให้ทุกชื่อ (network/stack/volume/image) อ้างอิงจาก `ENV_NAME` ใน `.env` — "เปลี่ยนชื่อแล้วรันใหม่ได้ทันที" — แล้วเจอ 2 กับดักตอนทำให้ compose ใช้ `${ENV_NAME}` ในชื่อ:
  1. ใส่ `${ENV_NAME}_postgres_data` ตรงๆ ใน `volumes:` section (เป็น key) → `docker stack config`/deploy พังด้วย `volumes additional properties '${ENV_NAME}_postgres_data' not allowed` (Compose ไม่ interpolate `${}` ที่ key ของ top-level `volumes` map)
  2. `.env` ใส่ `DATABASE_URL=...@${ENV_NAME}_infra_db:5432/...` แล้วคิดว่า compose/environment จะแทนค่าให้เอง → **`docker stack deploy` (และ `docker stack config`) ไม่อ่านไฟล์ `.env` เพื่อ interpolate** (ต่างจาก `docker compose config` ที่อ่าน) และ `env_file` ก็ส่งค่าดิบไปทั้ง `${...}` → container ได้ host ที่ผิด
- **Root Cause:** (1) compose-go interpolate ค่าใน yaml แต่ key ของ `volumes:` map ไม่ถูก interpolate เหมือนกันหมด → ต้องใช้ "key คงที่ + `name: ${ENV_NAME}_...`"; (2) stack deploy ใช้ shell environment ของ process ที่เรียก (คนที่ export `.env` มาก่อน) ไม่ใช่ `.env` ในโฟลเดอร์เอง
- **Correct Pattern/Solution:**
  1. **Volume ชื่อตาม env:** `volumes:` ใช้ key คงที่ (`postgres_data:`) แล้วตั้ง `name: ${ENV_NAME}_postgres_data` ข้างใต้ (services mount อ้าง key คงที่) — validate ผ่านทั้ง `docker stack config` และ `docker compose config`
  2. **DATABASE_URL/REDIS_URL ตาม env:** ไม่วางใจค่าใน `.env` — ไป override ใน compose `environment:` เช่น `DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${ENV_NAME}_infra_db:5432/${POSTGRES_DB}` (compose interpolate ค่าของตัวเองได้)
  3. **สคริปต์ทุกตัวที่ deploy ต้อง export `.env` ก่อน** `docker stack deploy`: `set -a; . ./.env; set +a` (แทน `export $(grep -v '^#' .env | xargs)` ซึ่งพังถ้ามี trailing comment เช่น `# 30 days`)
  4. **เทสของจริง:** `ENV_NAME=x docker stack config -c <file>` เป็นตัว validate เดียวกับ `stack deploy` — ใช้ตรวจว่าชื่อ interpolate ถูกก่อน deploy; ตรวจว่า `docker stack deploy` รันจาก shell ที่ `.env` ถูก export แล้ว
  - **กฎ: ถ้าอยากได้ "ชื่อทุกอย่างตาม ENV_NAME" — ชื่อที่ dynamic ต้อง interpolate ที่ layer ของ compose (`environment:` / `name:`), ไม่อ้าง `${}` ภายในไฟล์ `.env`; และ deploy ทุกครั้งต้อง export .env ก่อน**
- **Date Added:** 2026-08-18

### 🛠️ CSS stacking — absolute z-auto ทับ in-flow (avatar โดน gradient cover ทับ = หน้าโปรไฟล์ "บัคๆ")
- **Context/Problem:** หน้าโปรไฟล์ (Profile.vue) avatar โดนดึงขึ้นมาซ้อน cover ด้วย `-mt-10 sm:-mt-14` แล้วดู "บัคๆ" — มีแถบคล้ำ/ด่างทับบน avatar ทั้งบน/กลาง/ล่าง ทั้งที่ตั้งใจให้ avatar อยู่หน้าสุด (ตรวจด้วย `document.elementFromPoint` ที่พิกัด avatar → คืน gradient overlay)
- **Root Cause:** ภายในการ์ด `bg-white ... overflow-hidden` มี element ตกแต่งเป็น `absolute` z-auto (วงกลม `bg-white/10` + แถบ `bg-gradient-to-t from-black/10`) อยู่ที่ cover; identity section (avatar+ชื่อ) เป็น in-flow (static) → **ตาม CSS painting order, positioned element (z-auto) วาดทับ in-flow content ที่มาทีหลังใน DOM เสมอ** → gradient/วงกลมจึงทับ avatar ที่ดึงขึ้นมาซ้อน (ยิ่ง gradient `from-black/10` ชัด เพราะเข้มจริง)
- **Correct Pattern/Solution:**
  1. ให้ section ที่ต้องอยู่บนสุดเป็น `relative z-10` (หรือ z บวก) — สร้าง stacking context ของตัวเองให้อยู่เหนือ element ตกแต่ง z-auto: `identity wrapper → <div class="relative z-10 px-4 sm:px-6 ...">` — avatar+ชื่อจะอยู่บนสุดเสมอ โดย gradient/วงกลมยังโชว์บน cover ตรงส่วนที่เหลือ
  2. จัด z-index เมนู ⋮/dropdown ให้สอดคล้องทั้งระบบ: overlay ปิดเมนู `fixed inset-0 z-40` (เหนือ header มือถือ z-30 → แตะที่ไหนก็ปิด; ใต้ dropdown z-50), wrapper เมนู `absolute z-50` — ไล่เลขตาม MainLayout (sidebar z-50, mobile overlay z-40, header z-30)
  3. **วิธีตรวจโดยไม่เห็นภาพ:** playwright `document.elementFromPoint(x,y)` + เปรียบเทียบ `getBoundingClientRect()` ว่าตรงไหนทับกัน แล้วดูว่า element ไหนเป็น topmost (เทียบ class) — หา bug "มี element ทับกัน" ได้แม่นกว่าการเดาจากโค้ด
  - **กฎ: ใน layout ที่ดึง element ด้วย margin ลบ/ซ้อนทับกัน ถ้าเห็นเงา/แถบ/element ตกแต่งวาดทับ content ให้สงสัย painting order ก่อน — element `position` ใดๆ (z-auto) จะทับ in-flow เสมอ ต้องเติม `relative z-*` ที่ content ที่ควรอยู่บนสุด**
- **Date Added:** 2026-08-18

### 🛠️ SPA หลังล็อกอิน — SEO/Google ต้องใส่เนื้อหาแนะนำไว้ที่หน้า Login + meta/JSON-LD ใน index.html
- **Context/Problem:** ทั้งเว็บเป็น SPA ที่ต้องล็อกอินก่อนเข้าถึง → Google ไม่มีหน้าสาธารณะให้ crawl เนื้อหา (dashboard/issues โดน guard หมด) — คำค้น "สภานักเรียน พิริยาลัย" ไม่เจอเว็บ
- **Root Cause:** หน้าเดียวที่เข้าได้ก่อนล็อกอินคือ `/login` ซึ่งเดิมเป็นแค่ฟอร์ม 2 ช่อง ไม่มีข้อความแนะนำ + `index.html` มีแค่ title/description สั้นๆ
- **Correct Pattern/Solution:**
  1. **หน้า login = หน้าแนะนำเว็บไซต์:** แบ่งเป็น 2 แผง (desktop `grid lg:grid-cols-2`) — แผงซ้าย gradient แดง = โลโก้ + "PIRIvoice คืออะไร/ทำอะไร" + จุดเด่น (แจ้งเรื่อง/ไต่ระดับ/นับถอยหลัง/dashboard) + ขั้นตอนทำงาน + คีย์เวิร์ดค้นหา (#tags) + ข้อมูลโรงเรียน/ที่อยู่; แผงขวา = ฟอร์มล็อกอิน (มือถือ `lg:hidden` แผงแนะนำมาก่อน ฟอร์มตาม)
  2. **`index.html` เต็มรูปแบบ:** `title` + `description` + `keywords` (ไทย+อังกฤษ รวมชื่อเก่า PRSC, พรส, piriyalai) + `canonical` + `robots: index,follow` + Open Graph (`og:url/image`) + Twitter Card + `JSON-LD` 2 บล็อก (`WebSite` + `EducationalOrganization` พร้อมที่อยู่) — ใส่ `lang="th"` และ `theme-color` แล้ว
  3. **`public/robots.txt`** (`Allow: /` + `Sitemap:`) + **`sitemap.xml`** (`/` priority 1.0, `/login` 0.8) — ไฟล์ใน `public/` ถูก copy ไป dist อัตโนมัติตอน build
  4. **กฎ: SPA ที่ข้อมูลหลังล็อกอิน — เนื้อหา SEO ที่ Google เห็นคือหน้า login + meta tag; อย่าทิ้งหน้า login ให้เป็นแค่ฟอร์มว่าง**
- **Date Added:** 2026-08-23

### 🛠️ สถานะ `rejected` (ถูกปัดตก) — ผู้ดูแลปัดตกต้องแยกหมวดจากผู้แจ้งยกเลิก (`cancelled`)
- **Context/Problem:** ตอนแรก `cancel_issue` ให้ทั้งผู้แจ้งและผู้ดูแล (ผู้รับ/admin/ครูระดับชั้น — `_can_manage_issue`) ตั้ง status='cancelled' ด้วย note default "ผู้แจ้งยกเลิกเรื่อง" → ครู/หัวหน้าห้องปัดตกเรื่อง ขึ้นไทม์ไลน์เหมือนผู้แจ้งยกเลิก (เข้าใจผิดว่าเป็นผู้แจ้งถอนเรื่องเอง) — requirement: ผู้ดูแลปัดตกต้องเป็นหมวดใหม่ "ถูกปัดตก"
- **Root Cause:** endpoint เดียว `/cancel` รับทั้ง 2 บทบาทแต่ไม่แยกผลตาม actor; ไทม์ไลน์ (IssueDetail) โชว์แค่ `h.note` ไม่โชว์ status
- **Correct Pattern/Solution:**
  1. **backend `cancel_issue`:** ถ้า `reporter_id == user_id` → status='cancelled' + note "ผู้แจ้งยกเลิกเรื่อง"; นอกนั้น (ผ่าน `_can_manage_issue`) → status='rejected' + note "ถูกปัดตก[: เหตุผล]" — แล้ว **คืน status จริง** เพื่อให้ router `return {"status": new_status}` ตรงกับที่เกิดขึ้น
  2. **เพิ่ม status ใหม่ครบทุกจุด:** dashboard `STATUS_LABELS`/`STATUS_ORDER` + summary `by_status_all.get("rejected", 0)` + `DashboardSummary.rejected` (pydantic + frontend interface); frontend `IssueStatus` union + `STATUS_LABELS`/`STATUS_DOT/BAR/BADGE/SHORT` (สี rose ต่างจาก cancelled เทา) + `statusColor` ใน MyIssues/ReceivedIssues + option filter ใน ReceivedIssues
  3. **frontend ปุ่มแยก:** `canCancel` (เฉพาะผู้แจ้ง) = "ยกเลิกเรื่อง" / `canReject` (canManage และไม่ใช่ผู้แจ้ง) = "ปัดตก" — ปุ่มเดียว `v-if="canCancel || canReject"` แล้วป้าย/ข้อความยืนยันตาม `isReporter`; ทั้งคู่เรียก `/cancel` เดิม (backend ตัดสิน status จาก actor)
  4. **ไทม์ไลน์:** เพิ่ม chip สีแสดง `STATUS_LABELS[h.status]` ต่อรายการ status_history — ให้เห็นชัดว่าจุดไหน "ถูกปัดตก" ไม่ต้องเดาจาก note อย่างเดียว
  - **กฎ: ถ้า endpoint หนึ่งรองรับหลายบทบาทที่ควรได้ผลต่างกัน อย่า hardcode status ใน router — ให้ service ตัดสินจาก actor แล้วคืนค่าจริง; เวลาเพิ่ม status ใหม่ ไล่ grep `cancelled` ทั้ง frontend+backend (labels/colors/filter/dashboard/test) ให้ครบก่อน**
- **Date Added:** 2026-08-23

### 🛠️ PATCH แก้ไขเรื่อง + คอมเมนต์ — dynamic SET ต้องจอง `$1` ไว้ WHERE, ชื่อ snapshot ต้อง fallback users.full_name, ตารางใหม่ต้องเข้าครบ 3 ที่
- **Context/Problem:** เพิ่มฟีเจอร์ (ก) ผู้แจ้งแก้ไขเรื่อง (`PATCH /api/issues/{id}`) และ (ข) คอมเมนต์แบบ YouTube (`issue_comments` + CRUD ของตัวเอง) — เจอ 3 จุดที่พังถ้าไม่ระวัง: asyncpg parameter numbering, ชื่อ snapshot ว่าง, และ schema ใหม่หลุดจาก test isolation
- **Root Cause:**
  1. **asyncpg Ambiguous/Indeterminate:** dynamic `UPDATE ... SET` ต้องไม่ reuse `$1` ข้าม type และต้องไม่มี param ค้างที่ไม่ได้ใช้ (มีบทเรียน AmbiguousParameterError/IndeterminateDatatypeError แล้ว) — วิธีคือจอง `$1` ไว้ `WHERE id` แล้ว field แต่ละตัวใช้ `len(params)+1` ก่อน `append`
  2. **`CONCAT_WS(' ', prefix, first_name, last_name)` กับแถวที่ชื่อว่าง:** register_user/self-signup เก็บชื่อไว้ที่ `users.full_name` แต่ `students.first_name/last_name` เป็น `''` → `CONCAT_WS` ได้ `' '` (space) — `NULLIF(..., '')` จับไม่ออกเพราะไม่ใช่ `''` → ต้อง `TRIM` ก่อน `NULLIF` แล้ว fallback `users.full_name`
  3. **ตารางใหม่หลุด test isolation:** เพิ่ม `issue_comments` ใน init_db + migration แต่ลืม conftest `TRUNCATE` → คอมเมนต์รัวข้าม test (deep-DB count ผิดเงียบๆ)
  4. **asyncpg คืน jsonb เป็น string:** เทสที่อ่าน `audit_logs.old_values['title']` ต้อง `json.loads` ก่อน (มีบทเรียนเดิม) — `audit["old_values"]["title"]` = `TypeError: string indices`
- **Correct Pattern/Solution:**
  1. **Dynamic SET:** `params = [issue_id]` → `sets.append(f"col = ${len(params)+1}"); params.append(value)` → สุดท้าย sanity check `sql.count('$') == len(params)`; `updated_at = NOW()` ไม่มี param ไม่กระทบเลข
  2. **ชื่อแสดง:** `NULLIF(TRIM(CONCAT_WS(' ', s.prefix, s.first_name, s.last_name)), '') AS student_name` + `JOIN users u` → ในโค้ด `c["student_name"] or c["full_name"]`; ใช้ `SELECT ... FOR UPDATE` บนแถว issue ตอนเช็คสถานะปิด (กัน TOCTOU กับ resolve/cancel)
  3. **ตารางใหม่ = เข้าครบ 3 ที่:** init_db (`CREATE TABLE IF NOT EXISTS`) + `migrations/00X_*.py` (`CREATE TABLE IF NOT EXISTS` + index) + `conftest.py` TRUNCATE list — สามที่ต้องมีครบ
  4. **authorization:** แก้เรื่อง = `reporter_id == user_id` หรือ admin (`_is_admin`); คอมเมนต์ = ใครเห็นเรื่องได้ (`_assert_can_view` = visibility เดียวกับ `get_issue`) + แก้/ลบเฉพาะ `user_id` ของตัวเอง
  - **กฎ: (1) dynamic PATCH ต้อง `model_dump(exclude_unset=True)` + จอง `$1` WHERE แล้ว field เริ่ม `len(params)+1`; (2) snapshot ชื่อจาก students ต้อง TRIM + fallback users.full_name เพราะ first/last name ว่างได้; (3) schema ใหม่ต้องเข้าทั้ง init_db + migration + conftest TRUNCATE; (4) เทส audit jsonb ต้อง json.loads**
- **Date Added:** 2026-08-26

### 🛠️ List แบบแบ่งหน้า — `COUNT(*) OVER()` อ่าน total จากแถวที่ return → หน้าว่าง (offset เลย) ได้ total=0 ผิดต้องนับแยก + ค้นหา ILIKE ต้องหนี wildcard
- **Context/Problem:** Phase 2 เพิ่ม Pagination + Search + Sort ให้ `GET /api/issues` — เจอ 2 กับดัก: (ก) เทส `offset` เลยข้อมูลหน้าแล้ว `total` กลับเป็น 0 ทั้งที่ยังมีเรื่องอยู่; (ข) search คล้ายคำต้องไม่ให้ `%`/`_` กลายเป็น wildcard
- **Root Cause:**
  1. **`COUNT(*) OVER()` กับ LIMIT/OFFSET:** window function นับแถวที่ตรง WHERE ก่อน LIMIT — ได้ total ถูกต้องเฉพาะเมื่อมีแถว return; ถ้า `offset` เลยข้อมูล `rows` ว่าง → อ่านค่า total จากแถวแรกไม่ได้ → ต้องคืน 0 ผิดพลาด
  2. **เทสต์เดิม assert รูปแบบ list ตรงๆ:** เปลี่ยน response จาก `list[IssueOut]` เป็น envelope `{items,total,page,page_size,pages}` → เทสต์ 6 จุดที่ใช้ `res.json()` เป็น list โดยตรง fail (ต้อง `res.json()["items"]`)
  3. **`q` เข้า ILIKE โดยไม่หนี:** `%`/`_`/`\` ในคำค้นกลายเป็น wildcard/escape → `q=%` จับทุกเรื่อง
- **Correct Pattern/Solution:**
  1. **total:** `SELECT ... COUNT(*) OVER() AS total_count` ใส่ใน query หลัก (ได้ total ใน query เดียวเมื่อมีแถว); **ถ้า `rows` ว่าง (offset เลย) → นับแยกด้วย `SELECT COUNT(*) ... WHERE {' AND '.join(where)}` โดยใช้ params เดิมก่อน append limit/offset (`filter_params = list(params)`)**
  2. **search:** `_escape_like(s)` = `s.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")` + `ILIKE $n ESCAPE '\'`; `q.split()` ทุกคำ (AND ระหว่างคำ) OR ข้าม 6 ฟิลด์ (title/description/room/reporter_room/reporter_name/assignee_name) — ต่อ AFTER visibility cond กันค้นข้ามระดับ; reuse `$n` ใน OR ปลอดภัยเพราะทุกตำแหน่งเป็น text
  3. **sort:** `ORDER BY i.created_at {ASC|DESC}, i.id {ASC|DESC}` — เพิ่ม `i.id` รองกันหน้าไม่เสถียร (timestamp ซ้ำกัน); router ใช้ `Query(pattern="^(asc|desc)$")` → ค่าแปลกได้ 422 อัตโนมัติ
  4. **เทสต์:** เปลี่ยนทุกจุดที่ assert list ตรงๆ เป็น `["items"]` พร้อมกัน; เพิ่มเทสต์ search หนี wildcard (`q=%` เจอเฉพาะเรื่องที่มี `%` จริง) + search ไม่รั่วข้ามระดับ (student ค้นแล้วไม่เจอเรื่องคนอื่น) + pagination หน้าเลย (`offset` เกิน → items=[] แต่ total ยังเท่าเดิม)
  - **กฎ: (1) อย่าใช้ `COUNT(*) OVER()` เป็น total แบบลอยๆ เมื่อมี LIMIT/OFFSET — หน้าว่างต้องมี fallback count; (2) เปลี่ยน response shape ของ list ต้องไล่แก้เทสต์ที่ assert list ตรงๆ ทุกจุด; (3) ILIKE search ทุกครั้งต้องหนี `%`/`_`/`\` + `ESCAPE '\'`; (4) เติม `i.id` ใน ORDER BY เสมอเพื่อให้ pagination กำหนดทิศทางได้**
- **Date Added:** 2026-08-26
