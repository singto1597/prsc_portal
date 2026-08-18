# 🏫 PIRIvoice — ระบบรับฟังความคิดเห็นและปัญหา (เสียงจากชาวพิริยาลัย)

> **PIRIvoice** (Pirivoice / เสียงจากชาวพิริยาลัย) — ระบบรับฟังความคิดเห็นและปัญหาสภานักเรียน พิริยาลัย (เดิมชื่อ PRSC Portal)

ระบบรับฟังความคิดเห็น/ปัญหา (Issue & Feedback Portal) ที่นักเรียนแจ้งเรื่องเข้ามา แล้วไต่ระดับการแก้ไขเป็นขั้นตามสายงาน (Escalation Pyramid):
**หัวหน้าห้อง + รอง 4 ฝ่าย → ประธานระดับ → สภานักเรียน/ประธานสภา**

ออกแบบด้วยสถาปัตยกรรม **Microservices & Monorepo** รองรับการ Deploy ด้วย Docker Swarm และ Traefik

## 📂 โครงสร้างโปรเจกต์ (Monorepo Architecture)

- `backend/` : FastAPI (Python 3.12+ / asyncpg) - จัดการ Database, Business Logic และ API กลาง
- `frontend/` : Vue.js + Vite + TypeScript - หน้าเว็บสำหรับนักเรียนและสภานักเรียน
- `docs/`    : กฎ engineering rules + Scope ของโปรเจกต์
- `docker-compose.infra.yml` : ไฟล์รันฐานข้อมูล (PostgreSQL & Redis)
- `docker-compose.app.yml` : ไฟล์รันตัวแอปพลิเคชัน (Backend, Frontend)

## 🏗️ สถาปัตยกรรมเซิร์ฟเวอร์ (Infrastructure)

ระบบนี้ใช้ **Docker Swarm** ในการทำ Cluster และใช้ **Traefik** เป็น Reverse Proxy / Load Balancer ทำให้เราสามารถ:
1. แยกระบบ `Staging` และ `Production` ออกจากกันอย่างเด็ดขาดบนเซิร์ฟเวอร์เดียว
2. อัปเดตโค้ดแบบ **Zero Downtime** (เว็บไม่ล่มระหว่างรอโหลดคอนเทนเนอร์ใหม่)
3. รัน API และ Web ซ้อนกันหลาย Replicas เพื่อรองรับโหลดที่มากขึ้น

---

## 🚀 วิธีติดตั้งและใช้งาน (Getting Started)

### 1. โคลนโปรเจกต์
```bash
git clone <repo-url> pirivoice
cd pirivoice
```

### 2. ตั้งค่า Environment Variables

คัดลอกไฟล์ `.env.example` มาสร้างเป็นไฟล์ `.env` ที่โฟลเดอร์นอกสุดของโปรเจกต์ (Root Directory) **เพียงไฟล์เดียวเท่านั้น**:

```bash
cp .env.example .env
nano .env
```

*(ระบบทั้งหมดจะดึงค่าคอนฟิกจากไฟล์ตัวแม่ไฟล์นี้โดยอัตโนมัติ)*

### 3. เปิดใช้งาน Docker Swarm & Traefik (สำหรับรันครั้งแรก)

```bash
docker swarm init
docker network create --driver=overlay traefik-public
```

*(ต้องรัน Traefik Proxy ไว้ที่เซิร์ฟเวอร์เพื่อรอรับทราฟฟิกพอร์ต 80 เสมอ — ดูตัวอย่างในโปรเจคเก่า)*

### 4. สตาร์ท Infrastructure (ฐานข้อมูล)

```bash
# โหลดตัวแปรสภาพแวดล้อมชั่วคราว
export $(grep -v '^#' .env | xargs)
docker stack deploy -c docker-compose.infra.yml ${ENV_NAME}_infra
```

### 5. Deploy แอปพลิเคชัน

```bash
chmod +x pull_all.sh
./pull_all.sh
```

สคริปต์นี้จะทำการดึงโค้ดล่าสุด -> Build Image ตามเลข Commit ล่าสุด -> สลับสวิตช์ตู้คอนเทนเนอร์แบบ Zero Downtime ทันที!

---

## 🚨 การกู้ภัยฉุกเฉิน (Rollback)

### วิธีที่ 1: สลับคอนเทนเนอร์ทันที (Hot Rollback - ไวที่สุด)
```bash
docker service rollback staging_app_backend
# หรือ
docker service rollback staging_app_frontend
```

### วิธีที่ 2: ถอยหลังเต็มรูปแบบ (Full Rollback Script)
```bash
chmod +x oh_shit.sh
./oh_shit.sh
```

---

## 🧪 การเทส

### คำสั่งที่ใช้ในการเทส
```
docker compose -f docker-compose.test.yml run --rm test_runner sh -c "export PYTHONDONTWRITEBYTECODE=1 && python -m pytest -p no:cacheprovider -v /app/tests/"
```

---

## 🧪 การรันเพื่อพัฒนา (Local Dev)

```bash
# 1. เตรียม environment
cp .env.example .env   # แล้วแก้ DATABASE_URL, JWT_SECRET, API_KEY, SUPER_ADMIN_ID

# 2. รัน Postgres (Docker)
docker run -d --name piri_dev_db -e POSTGRES_USER=piri -e POSTGRES_PASSWORD=piri_dev_pw -e POSTGRES_DB=piri_dev -p 5434:5432 postgres:16-alpine

# 3. Backend
cd backend
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 4. Seed ข้อมูลตัวอย่าง (สำหรับนำเสนอ)
cd backend
DATABASE_URL=postgresql://piri:piri_dev_pw@localhost:5434/piri_dev ./venv/bin/python -m scripts.seed_data

# 5. Frontend
cd frontend
npm run dev
```

## 🔑 บัญชีตัวอย่าง (รหัสผ่าน: 1234 ทุกบัญชี)

| บัญชี | ตำแหน่ง | เห็นอะไร |
|---|---|---|
| `41001` | หัวหน้าห้อง ม.4/1 | เรื่องระดับห้อง |
| `41002` | รองวิชาการ | เรื่องระดับห้อง |
| `99401` | ประธานระดับ ม.4 | เรื่องระดับ (escalate มา) |
| `99001` | ประธานสภา (Admin) | ทุกเรื่อง + Dashboard |
| `41006` | นักเรียน ม.4/1 | เรื่องของตัวเอง |

---

## 👥 บัญชีผู้ดูแลระบบอัตโนมัติ (สร้างตอนเปิดระบบครั้งแรก)

เมื่อ **backend สตาร์ทครั้งแรก** ระบบจะสร้างบัญชีผู้ดูแลระบบให้อัตโนมัติ 3 บัญชี:
**แอดมิน** (`admin`), **ครูสภา** (`teacher_council`), **ประธานสภา** (`council_president`)

- Username เป็นแบบสุ่มที่เดายาก (เช่น `piri_admin_9f2k3c`) — นักเรียนเดาไม่ออก
- รหัสผ่านชั่วคราวสุ่ม 12 ตัว — **ระบบบังคับให้เปลี่ยนรหัสเมื่อ login ครั้งแรก**
- สร้างเฉพาะเมื่อยังไม่มีผู้ใช้ตำแหน่งเหล่านี้ในระบบ (idempotent — restart ซ้ำไม่สร้างเพิ่ม)

### 🔑 วิธีดู username / รหัสผ่านชั่วคราว

**วิธีที่ 1 — ดูจาก log ของ backend (แนะนำใน Docker Swarm):**
```bash
# ตัวอย่าง stack ชื่อ staging_app → เปลี่ยนตาม ENV_NAME
docker service logs staging_app_backend | grep "username"
# หรือดูข้อความสรุปทั้งบล็อก
docker service logs staging_app_backend | grep -A2 "สร้างบัญชีผู้ดูแลระบบ"
```

**วิธีที่ 2 — อ่านจากไฟล์ที่ระบบเขียนไว้ให้:**
```bash
# ระบบเขียนไฟล์ไว้ที่โฟลเดอร์ที่รัน backend
cat default_admin_credentials.txt
```
- ใน dev = โฟลเดอร์ที่รัน `uvicorn`; ใน Docker = โฟลเดอร์ทำงานของ container
- กำหนด path เองได้ผ่าน `SEED_CREDENTIALS_FILE` ใน `.env` (ไฟล์นี้ถูก gitignore แล้ว)

**การใช้งานครั้งแรก:** login ด้วย username + รหัสชั่วคราว → ระบบบังคับเปลี่ยนรหัสผ่านก่อนใช้งาน
→ หลังเปลี่ยนครบแล้วควรลบไฟล์ credentials ทิ้ง

> ⚠️ ถ้าลบ admin/ครูสภาออกจากระบบ แล้ว restart backend → ระบบจะสร้างบัญชีใหม่พร้อม credentials ใหม่

---

## 🧹 การรีเซ็ตระบบ (ล้างข้อมูล เริ่มต้นใหม่)

ล้างฐานข้อมูลทั้งหมด (นักเรียน / เรื่อง / ประวัติ) แล้วให้ระบบสร้าง schema + บัญชี admin ใหม่

```bash
# 0. โหลด environment (ตามชื่อ ENV_NAME ใน .env เช่น staging / production)
export $(grep -v '^#' .env | xargs)

# 1. หยุดแอป + infra
docker stack rm ${ENV_NAME}_app
docker stack rm ${ENV_NAME}_infra

# 2. ลบ volume ฐานข้อมูล (⚠️ ข้อมูลทั้งหมดจะหายถาวร!)
docker volume rm ${ENV_NAME}_postgres_data

# 3. Deploy ใหม่ — init_db สร้าง schema ใหม่ + สร้างบัญชี admin/ครูสภาใหม่
docker stack deploy -c docker-compose.infra.yml ${ENV_NAME}_infra
./pull_all.sh

# 4. ดู credentials ใหม่ (ต่างจากรอบก่อนเสมอ)
docker service logs ${ENV_NAME}_app_backend | grep "username"
```

**หลังจากรีเซ็ตแล้ว ต้องทำอะไรต่อ:**
- นำเข้านักเรียนอีกครั้งผ่านหน้าเว็บ (เมนู "นำเข้า Excel") — หรือรัน seed ข้อมูลตัวอย่างสำหรับนำเสนอ:
  ```bash
  cd backend
  DATABASE_URL=postgresql://... ./venv/bin/python -m scripts.seed_data
  ```
- ตรวจสอบบัญชี admin ใหม่จาก log/ไฟล์ แล้วเปลี่ยนรหัสตอน login ครั้งแรก

> 💡 อยากเช็คว่าลบ volume สำเร็จไหม: `docker volume ls | grep ${ENV_NAME}_postgres`
> volume ที่ใช้จริงคือ `${ENV_NAME}_postgres_data` (ตามที่ mount ใน `docker-compose.infra.yml`)

---

## 🧪 เทส Backend

```bash
docker compose -f docker-compose.test.yml run --rm test_runner sh -c "export PYTHONDONTWRITEBYTECODE=1 && python -m pytest -p no:cacheprovider -v /app/tests/"
```

## 📐 ขอบเขตงาน (Scope)

ดูไฟล์ `docs/scope.md` สำหรับรายละเอียด In Scope / Out of Scope ของเวอร์ชันนี้
