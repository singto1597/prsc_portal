"""
Migration: 001 — รื้อหมวดหมู่การรับแจ้งเรื่องใหม่ทั้งหมด
=========================================================
- เพิ่มคอลัมน์ `main_category` (หมวดหลัก 3 หมวด) แทน `topic_type` เดิม
- `category` กลายเป็นหมวดย่อยของ main_category (โครงสร้างใหม่)
- backfill ข้อมูลเดิม + ตรึงให้ category ตรงกับ main_category
- ลบคอลัมน์ topic_type ทิ้ง (ตาม spec รื้อใหม่ทั้งหมด)
"""
VERSION = "001_issue_categories"
DESCRIPTION = "รื้อหมวดหมู่การรับแจ้ง: เพิ่ม main_category (3 หมวดหลัก), แปลง category เป็นหมวดย่อย, ลบ topic_type"

# หมวดย่อยที่ถูกต้องของแต่ละหมวดหลัก (ใช้ตรึงความสอดคล้อง)
_VALID_SUBCATS = {
    "suggestion": {"academic", "reception", "activity", "discipline", "democracy"},
    "wellbeing": {"physical_health", "mental_health"},
    "report": {"complaint", "grievance"},
}


async def upgrade(conn) -> None:
    # 1. เพิ่มคอลัมน์ main_category (ถ้ายังไม่มี)
    await conn.execute("ALTER TABLE issues ADD COLUMN IF NOT EXISTS main_category TEXT")

    # 2. มีคอลัมน์ topic_type เดิมหรือไม่ (DB เก่า) → ทำ backfill
    has_topic = await conn.fetchval(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'issues' AND column_name = 'topic_type'
        """
    )

    if has_topic:
        # 2.1 แปลง topic_type เดิม → main_category ใหม่
        #     suggestion → เสนอความคิดเห็น, living → สุขภาวะ, problem → แจ้งเหตุ
        await conn.execute(
            """
            UPDATE issues
            SET main_category = CASE topic_type
                WHEN 'suggestion' THEN 'suggestion'
                WHEN 'living'     THEN 'wellbeing'
                WHEN 'problem'    THEN 'report'
                ELSE 'suggestion'
            END
            WHERE main_category IS NULL
            """
        )
        # 2.2 แปลงหมวดย่อยเดิม → หมวดใหม่ (สุขาภิบาล→สุขภาวะทางกาย, อื่นๆ→วิชาการ)
        await conn.execute(
            """
            UPDATE issues
            SET category = CASE
                WHEN category = 'sanitation' THEN 'physical_health'
                WHEN category = 'other'      THEN 'academic'
                ELSE category
            END
            """
        )
        # 2.3 ลบ topic_type (รื้อโครงสร้างเดิมทิ้ง)
        await conn.execute("ALTER TABLE issues DROP COLUMN IF EXISTS topic_type")

    # 3. ตรึง category ให้ตรงกับ main_category (กันข้อมูลผิดหลัก)
    for main_cat, valid in _VALID_SUBCATS.items():
        # $1 = main_category, ตามด้วย $2... หมวดย่อยที่ถูกต้อง
        placeholders = ", ".join(f"${i+2}" for i in range(len(valid)))
        await conn.execute(
            f"""
            UPDATE issues
            SET category = '{_default_subcat(main_cat)}'
            WHERE main_category = $1 AND category NOT IN ({placeholders})
            """,
            main_cat, *valid,
        )

    # 4. default + NOT NULL
    await conn.execute("ALTER TABLE issues ALTER COLUMN main_category SET DEFAULT 'suggestion'")
    await conn.execute("ALTER TABLE issues ALTER COLUMN main_category SET NOT NULL")

    # 5. index สำหรับกรองตามหมวดหลัก
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_issues_main_category ON issues(main_category)")


def _default_subcat(main_cat: str) -> str:
    """หมวดย่อย fallback ของแต่ละหมวดหลัก"""
    defaults = {
        "suggestion": "academic",
        "wellbeing": "physical_health",
        "report": "complaint",
    }
    return defaults.get(main_cat, "academic")
