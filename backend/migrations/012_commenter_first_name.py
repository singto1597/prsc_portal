"""
Migration: 012 — commenter_first_name (คอมเมนต์ในเรื่อง)
===========================================================
- issue_comments.commenter_first_name TEXT: ชื่อจริง (first_name) ของผู้คอมเมนต์
  ณ ตอนสร้าง (snapshot เดียวกับ commenter_name)
- avatar ของคอมเมนต์ใช้ "ตัวแรกของชื่อ" → ต้องมี first_name แยก กันตัดเอา
  จาก commenter_name (prefix/นามสกุลปน) ผิด
- เดิม commenter_name = prefix+first+last ครบ แต่ไม่มี first_name แยกเก็บ
- เป็น column เดินหน้า: คอมเมนต์เก่า (ก่อน migration) จะได้ NULL → frontend
  fallback ใช้ตัวแรกของ commenter_name แทน
"""
VERSION = "012_commenter_first_name"
DESCRIPTION = "คอมเมนต์: issue_comments.commenter_first_name (avatar ตัวแรกของชื่อ)"


async def upgrade(conn) -> None:
    await conn.execute("""
        ALTER TABLE issue_comments
            ADD COLUMN IF NOT EXISTS commenter_first_name TEXT;
    """)
