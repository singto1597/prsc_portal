"""
Migration: 003 — ตารางคิวงาน Import นักเรียนจาก Excel (Queue: ARQ Worker)
===========================================================================
เพิ่มตาราง `student_import_jobs` สำหรับสถาปัตยกรรม Queue แบบใหม่:
- upload → บันทึกไฟล์ + สร้าง record (status=PENDING)
- start → ยิง job_id เข้า Redis (ARQ) → worker ทยอย insert + update progress
- GET /import-jobs → ดูสถานะ/ความคืบหน้าทั้งหมด

Status flow: PENDING → QUEUED → PROCESSING → COMPLETED / FAILED

(ใช้ CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS เพื่อให้ idempotent
และรองรับกรณี init_db สร้างตารางนี้ไปแล้วใน DB ใหม่)
"""
VERSION = "003_student_import_jobs"
DESCRIPTION = "Import Excel แบบ Queue: ตาราง student_import_jobs + index"


async def upgrade(conn) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS student_import_jobs (
            id SERIAL PRIMARY KEY,
            file_name TEXT NOT NULL,              -- ชื่อไฟล์เดิมที่ผู้ใช้เห็น (แสดงผลใน UI)
            file_path TEXT NOT NULL,              -- path เก็บไฟล์บน storage (internal)
            status TEXT NOT NULL DEFAULT 'PENDING',
            total_rows INTEGER NOT NULL DEFAULT 0,
            processed_rows INTEGER NOT NULL DEFAULT 0,
            imported_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0,
            error_logs JSONB NOT NULL DEFAULT '[]'::jsonb,
            error_message TEXT,
            default_password TEXT,
            allowed_level TEXT,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_student_import_jobs_status ON student_import_jobs(status)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_student_import_jobs_created_at ON student_import_jobs(created_at)"
    )
    # กัน student ซ้ำ (room, เลขประจำตัว) — worker ใช้ ON CONFLICT กับ index นี้ตอน upsert
    await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_students_room_student_active
            ON students(room_id, student_id)
            WHERE deleted_at IS NULL
    """)
