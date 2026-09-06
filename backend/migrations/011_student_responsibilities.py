"""
Migration: 011 — หน้าที่รับผิดชอบ (Responsibilities) ของสมาชิกสภา/ผู้ช่วยหัวหน้าระดับ
=============================================================================
- students.responsibilities JSONB array: หมวดที่คนนั้นรับผิดชอบ (ตรงกับ issues.category)
  เช่น ['academic', 'discipline'] = วิชาการ + วินัย
- ใช้กับ class_role IN ('council_member', 'level_vice_president')
- 9 หมวด = ค่า category ทั้งหมดใน config/categories.json:
  academic, reception, activity, discipline, democracy, physical_health, mental_health, complaint, grievance
- เก็บเป็น JSONB array (ไม่ใช่ junction table) — สอดคล้องกับคอลัมน์ permissions เดิม
"""
VERSION = "011_student_responsibilities"
DESCRIPTION = "หน้าที่รับผิดชอบ: students.responsibilities JSONB + GIN index"


async def upgrade(conn) -> None:
    await conn.execute("""
        ALTER TABLE students
            ADD COLUMN IF NOT EXISTS responsibilities JSONB NOT NULL DEFAULT '[]'::jsonb;
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_students_responsibilities
            ON students USING GIN (responsibilities);
    """)
