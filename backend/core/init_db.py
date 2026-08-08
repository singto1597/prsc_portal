import asyncpg
import asyncio
import logging
import sys
import os

# 🛠️ ตั้งค่า Path เพื่อให้รันสคริปต์นี้ตรงๆ ได้ผ่าน CLI (สำหรับเรียกใช้ core.config)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.config import settings
except ImportError:
    sys.path.append(os.path.join(os.getcwd(), 'prsc-backend'))
    from core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("API_INIT_DB")

async def init_db(pool: asyncpg.Pool):
    """
    สร้าง Table ทั้งหมดในระบบ PRSC Portal หากยังไม่มี (Schema Setup)
    ฟังก์ชันนี้ถูกเรียกใช้ทั้งจาก main.py (Startup) และ run_setup (Manual CLI)
    """
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():

                # --- 1. ตาราง Users (ศูนย์รวมตัวตน) ---
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    avatar_url TEXT,
                    phone_number TEXT,
                    email TEXT UNIQUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP DEFAULT NULL
                );
                """)

                # --- 2. ตารางตารางเรียน/ห้องเรียน (rooms) ---
                # room_code เช่น ม.4/1, ม.5/2 ; level เช่น 'ม.4' สำหรับระดับชั้น
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id SERIAL PRIMARY KEY,
                    room_code VARCHAR(10) UNIQUE,
                    room_name TEXT NOT NULL,
                    level TEXT,                -- ระดับชั้น เช่น ม.1 ... ม.6
                    room_number INTEGER,       -- ห้องที่ เช่น 1, 2, 3
                    owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    deleted_at TIMESTAMP DEFAULT NULL
                );
                """)

                # --- 3. ตารางนักศึกษา (students) — มีตำแหน่งในห้องเรียน ---
                # ตำแหน่ง (class_role) เช่น 'class_president', 'vice_academic', ... 'student'
                # ระดับ (level) ที่ตำแหน่งทำงาน เช่น 'room' (ห้อง) / 'level' (ประธานระดับ) / 'council' (สภา)
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    room_id INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    student_id VARCHAR(10),          -- รหัสนักเรียน (เลขประจำตัว)
                    student_no INTEGER NOT NULL,     -- เลขที่ในห้อง
                    prefix TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    nickname TEXT,
                    class_role TEXT DEFAULT 'student',  -- ตำแหน่ง (แมปกับ config/roles.json)
                    is_admin BOOLEAN DEFAULT FALSE,
                    permissions JSONB DEFAULT '[]'::jsonb,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP DEFAULT NULL
                );
                """)

                # --- 4. ตารางปัญหา/ความคิดเห็น (issues) — หัวใจหลักของระบบ ---
                # topic_type: 'living' แจ้งสภาพความเป็นอยู่ / 'problem' แจ้งปัญหา / 'suggestion' ข้อเสนอแนะ
                # category: หมวดหมู่ย่อย — 'academic' วิชาการ / 'discipline' วินัย / 'activity' กิจกรรม / 'reception' ปฏิคม / 'sanitation' สุขาภิบาล / 'other' อื่นๆ
                # current_level: ตอนนี้เรื่องอยู่ที่ระดับไหน (room / level / council)
                # status: 'pending' (ยังไม่มีใครรับ) / 'in_progress' / 'resolved' / 'escalated'
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS issues (
                    id SERIAL PRIMARY KEY,
                    room_id INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
                    topic_type TEXT NOT NULL,            -- living / problem / suggestion
                    category TEXT NOT NULL,              -- academic / discipline / activity / reception / sanitation / other
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    image_url TEXT,
                    reporter_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    reporter_room_id INTEGER REFERENCES rooms(id) ON DELETE SET NULL,
                    reporter_name TEXT,
                    current_level TEXT DEFAULT 'room',   -- ระดับปัจจุบัน: room / level / council
                    current_assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    current_assignee_role TEXT,          -- บทบาทผู้รับปัจจุบัน (class_president, vice_academic, ...)
                    status TEXT DEFAULT 'pending',       -- pending / in_progress / resolved / escalated
                    priority TEXT DEFAULT 'normal',      -- low / normal / high / urgent
                    is_anonymous BOOLEAN DEFAULT FALSE,
                    resolved_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TIMESTAMP DEFAULT NULL
                );
                """)

                # --- 5. Escalation history (ประวัติการส่งต่อระหว่างระดับ) ---
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS issue_escalations (
                    id SERIAL PRIMARY KEY,
                    issue_id INTEGER REFERENCES issues(id) ON DELETE CASCADE,
                    from_level TEXT NOT NULL,          -- ระดับเดิม
                    to_level TEXT NOT NULL,            -- ระดับใหม่
                    from_assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    to_assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    reason TEXT,                       -- เหตุผลที่ส่งต่อ
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # --- 5.5 ตาราง status history (ติดตามประวัติสถานะ) ---
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS issue_status_history (
                    id SERIAL PRIMARY KEY,
                    issue_id INTEGER REFERENCES issues(id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    changed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    note TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # --- 6. ขั้นตอนการดำเนินงาน (steps) — ผู้รับเพิ่มขั้นตอนได้ว่าถึงไหนแล้ว ---
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS issue_steps (
                    id SERIAL PRIMARY KEY,
                    issue_id INTEGER REFERENCES issues(id) ON DELETE CASCADE,
                    step_title TEXT NOT NULL,
                    step_detail TEXT,
                    step_order INTEGER NOT NULL DEFAULT 0,
                    is_completed BOOLEAN DEFAULT FALSE,
                    completed_at TIMESTAMP WITH TIME ZONE,
                    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # --- 7. Countdown (นับถอยหลังงาน) — ผู้รับตั้งเวลาที่จะใช้แก้ปัญหา ---
                # deadline = time ที่รับงาน + estimated_days
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS issue_countdowns (
                    id SERIAL PRIMARY KEY,
                    issue_id INTEGER REFERENCES issues(id) ON DELETE CASCADE,
                    assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    estimated_days INTEGER NOT NULL,   -- ใช้เวลากี่วัน
                    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    deadline TIMESTAMP WITH TIME ZONE NOT NULL,
                    is_overdue BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # --- 8. audit_logs (โครงสร้างเหมือนโปรเจคเก่า) ---
                await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    trace_id VARCHAR(50),
                    room_id INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    actor_identifier VARCHAR(100) NOT NULL,
                    client_source VARCHAR(20) NOT NULL,
                    service_name VARCHAR(50) NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    entity_type VARCHAR(50),
                    entity_id VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'success',
                    error_detail TEXT,
                    old_values JSONB,
                    new_values JSONB,
                    endpoint_or_command TEXT,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    execution_time_ms INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # --- 9. ตารางรองรับ dashboard ---
                # (การนับสถิติสามารถ query ตรงจาก issues ได้ แต่ให้มี view/ตารางสรุปไว้ก่อน)

                # --- 10. Index เพื่อความเร็ว ---
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_issues_room_status ON issues(room_id, status);
                    CREATE INDEX IF NOT EXISTS idx_issues_reporter ON issues(reporter_id);
                    CREATE INDEX IF NOT EXISTS idx_issues_level ON issues(current_level);
                    CREATE INDEX IF NOT EXISTS idx_issues_topic ON issues(topic_type);
                    CREATE INDEX IF NOT EXISTS idx_issues_category ON issues(category);
                    CREATE INDEX IF NOT EXISTS idx_issue_escalations_issue ON issue_escalations(issue_id);
                    CREATE INDEX IF NOT EXISTS idx_issue_steps_issue ON issue_steps(issue_id);
                    CREATE INDEX IF NOT EXISTS idx_issue_countdowns_issue ON issue_countdowns(issue_id);
                    CREATE INDEX IF NOT EXISTS idx_issue_status_history_issue ON issue_status_history(issue_id);
                    CREATE INDEX IF NOT EXISTS idx_students_room_no_active
                        ON students(room_id, student_no)
                        WHERE deleted_at IS NULL;
                """)

                logger.info("✅ PRSC Portal Database Tables & Indexes Initialized Successfully!")

    except Exception as e:
        logger.error(f"❌ Failed to initialize Database: {e}")
        raise e

async def run_setup():
    logger.info("🚀 Starting Manual Database Setup...")
    pool = None
    try:
        pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=1,
            max_size=5
        )
        if pool:
            await init_db(pool)
            logger.info("✨ Database Setup Process Finished!")
        else:
            logger.error("❌ Could not create database connection pool.")
    except Exception as e:
        logger.error(f"💥 Fatal Error during manual setup: {e}")
    finally:
        if pool:
            await pool.close()
            logger.info("🛑 Database pool closed.")

if __name__ == "__main__":
    if not settings.DATABASE_URL:
        logger.error("❌ DATABASE_URL not found in .env file!")
        sys.exit(1)

    asyncio.run(run_setup())
