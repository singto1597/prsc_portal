# 🏫 PRSC Portal — ระบบรับความคิดเห็นและปัญหา (สภานักเรียน)

ระบบรับความคิดเห็น/ปัญหา (Issue & Feedback Portal) ที่นักเรียนแจ้งเรื่องเข้ามา แล้วไต่ระดับการแก้ไขเป็นขั้นตามสายงาน (Escalation Pyramid):
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
git clone <repo-url> prsc_portal
cd prsc_portal
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
docker run -d --name prsc_dev_db -e POSTGRES_USER=prsc -e POSTGRES_PASSWORD=prsc_dev_pw -e POSTGRES_DB=prsc_dev -p 5434:5432 postgres:16-alpine

# 3. Backend
cd backend
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 4. Seed ข้อมูลตัวอย่าง (สำหรับนำเสนอ)
cd backend
DATABASE_URL=postgresql://prsc:prsc_dev_pw@localhost:5434/prsc_dev ./venv/bin/python -m scripts.seed_data

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

## 🧪 เทส Backend

```bash
docker compose -f docker-compose.test.yml run --rm test_runner sh -c "export PYTHONDONTWRITEBYTECODE=1 && python -m pytest -p no:cacheprovider -v /app/tests/"
```

## 📐 ขอบเขตงาน (Scope)

ดูไฟล์ `docs/scope.md` สำหรับรายละเอียด In Scope / Out of Scope ของเวอร์ชันนี้
