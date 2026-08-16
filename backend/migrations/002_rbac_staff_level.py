"""
Migration: 002 — RBAC รองรับบทบาทครู
====================================
- เพิ่มคอลัมน์ `staff_level` ให้ students (ครูทั่วไปกำหนดระดับชั้นที่ดูแล เช่น 'ม.4')
- ปลด NOT NULL จาก student_no (ครู/แอดมิน/ครูสภา ไม่มีเลขที่ในห้อง)
- index ตาม class_role สำหรับกรอง role
"""
VERSION = "002_rbac_staff_level"
DESCRIPTION = "RBAC: เพิ่ม staff_level (ครูทั่วไป) + student_no ไม่บังคับ + index role"


async def upgrade(conn) -> None:
    # 1. staff_level — ระดับชั้นที่ครูทั่วไปรับผิดชอบ (เช่น 'ม.4', 'ม.5')
    await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS staff_level TEXT")

    # 2. student_no ไม่บังคับ (ครู/แอดมิน ไม่มีเลขที่)
    await conn.execute("ALTER TABLE students ALTER COLUMN student_no DROP NOT NULL")

    # 3. index ตาม role (สำหรับ query ของ teacher/admin)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_students_role_active ON students(class_role) WHERE deleted_at IS NULL"
    )
