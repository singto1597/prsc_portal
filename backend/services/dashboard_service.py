import asyncpg
from datetime import datetime, timedelta, timezone
from core.config import settings
from core.exceptions import ForbiddenError

# 🏷️ แผนที่ label ภาษาไทย
CATEGORY_LABELS = {
    "academic": "วิชาการ",
    "discipline": "วินัย",
    "activity": "กิจกรรม",
    "reception": "ปฏิคม",
    "sanitation": "สุขาภิบาล",
    "other": "อื่นๆ",
}
TOPIC_LABELS = {
    "living": "สภาพความเป็นอยู่",
    "problem": "ปัญหา",
    "suggestion": "ข้อเสนอแนะ",
}
STATUS_LABELS = {
    "pending": "รอรับเรื่อง",
    "in_progress": "กำลังดำเนินการ",
    "resolved": "แก้ไขเสร็จ",
    "escalated": "ส่งต่อระดับบน",
}


async def get_dashboard(pool: asyncpg.Pool, user_id: int) -> dict:
    """สรุปสถิติ dashboard (ต้องมีสิทธิ์ VIEW_DASHBOARD หรือ Super Admin)"""
    # เช็คสิทธิ์ (ข้ามทุกห้อง)
    async with pool.acquire() as conn:
        if not (settings.SUPER_ADMIN_ID and int(user_id) == int(settings.SUPER_ADMIN_ID)):
            row = await conn.fetchrow(
                """
                SELECT is_admin, permissions FROM students
                WHERE user_id = $1 AND deleted_at IS NULL AND status = 'active'
                ORDER BY id LIMIT 1
                """,
                user_id
            )
            if not row:
                raise ForbiddenError("ไม่พบข้อมูลของคุณ")
            perms = row["permissions"] or []
            if isinstance(perms, str):
                import json
                try:
                    perms = json.loads(perms)
                except json.JSONDecodeError:
                    perms = []
            if not row["is_admin"] and "VIEW_DASHBOARD" not in perms:
                raise ForbiddenError("คุณไม่มีสิทธิ์ดู Dashboard")

    async with pool.acquire() as conn:
        # 1. จำนวนรวม + แยกสถานะ
        total = await conn.fetchval("SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL") or 0
        pending = await conn.fetchval("SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL AND status='pending'") or 0
        in_progress = await conn.fetchval("SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL AND status='in_progress'") or 0
        resolved = await conn.fetchval("SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL AND status='resolved'") or 0
        escalated = await conn.fetchval("SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL AND status='escalated'") or 0

        total_students = await conn.fetchval("SELECT COUNT(*) FROM students WHERE deleted_at IS NULL") or 0
        total_rooms = await conn.fetchval("SELECT COUNT(*) FROM rooms WHERE deleted_at IS NULL") or 0

        # 2. top categories
        cat_rows = await conn.fetch(
            """
            SELECT category, COUNT(*) AS cnt FROM issues
            WHERE deleted_at IS NULL
            GROUP BY category ORDER BY cnt DESC LIMIT 6
            """
        )
        top_categories = [
            {"category": r["category"], "label": CATEGORY_LABELS.get(r["category"], r["category"]), "count": r["cnt"]}
            for r in cat_rows
        ]

        # 3. by status
        status_rows = await conn.fetch(
            """
            SELECT status, COUNT(*) AS cnt FROM issues
            WHERE deleted_at IS NULL
            GROUP BY status
            """
        )
        by_status = [
            {"status": r["status"], "label": STATUS_LABELS.get(r["status"], r["status"]), "count": r["cnt"]}
            for r in status_rows
        ]

        # 4. trend (7 วันล่าสุด)
        today = datetime.now(timezone.utc).date()
        trend = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            cnt = await conn.fetchval(
                "SELECT COUNT(*) FROM issues WHERE deleted_at IS NULL AND created_at::date = $1",
                day
            ) or 0
            trend.append({"date": day.isoformat(), "count": cnt})

        # 5. usage (logins จาก audit_logs) — ถ้ามีตาราง
        usage_count = 0
        recent_logins = []
        try:
            usage_count = await conn.fetchval(
                "SELECT COUNT(*) FROM audit_logs WHERE action = 'login'"
            ) or 0
            login_rows = await conn.fetch(
                """
                SELECT actor_identifier, created_at FROM audit_logs
                WHERE action = 'login'
                ORDER BY created_at DESC LIMIT 10
                """
            )
            recent_logins = [
                {"actor": r["actor_identifier"], "at": r["created_at"]}
                for r in login_rows
            ]
        except Exception:
            pass  # audit_logs อาจยังว่าง

    return {
        "total_issues": total,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "escalated": escalated,
        "total_students": total_students,
        "total_rooms": total_rooms,
        "top_categories": top_categories,
        "by_status": by_status,
        "trend": trend,
        "usage_count": usage_count,
        "recent_logins": recent_logins,
    }
