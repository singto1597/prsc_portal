import asyncpg
from datetime import datetime, timedelta, timezone
from core.config import settings
from core.exceptions import ForbiddenError
from core.categories import get_subcategory_label
from core.rbac import get_access_scope

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
        # 🛡️ scope: ครูทั่วไป (teacher) เห็นสถิติเฉพาะระดับชั้นตัวเองเท่านั้น
        scope = await get_access_scope(conn, user_id)
        level_where = ""
        level_params = []
        if scope["scope"] == "level" and scope.get("level"):
            level_where = " AND r.level = $1"
            level_params.append(scope["level"])

        issue_join = " LEFT JOIN rooms r ON r.id = i.room_id"

        # 1. จำนวนรวม + แยกสถานะ
        def _count(extra_where: str = "") -> int:
            return conn.fetchval(
                f"SELECT COUNT(*) FROM issues i{issue_join} WHERE i.deleted_at IS NULL{level_where}{extra_where}",
                *level_params
            ) or 0

        total = await _count()
        pending = await _count(" AND i.status='pending'")
        in_progress = await _count(" AND i.status='in_progress'")
        resolved = await _count(" AND i.status='resolved'")
        escalated = await _count(" AND i.status='escalated'")

        # ครูทั่วไป → จำนวนนักเรียน/ห้อง เฉพาะระดับชั้นตัวเอง
        if level_params:
            total_students = await conn.fetchval(
                f"SELECT COUNT(*) FROM students s LEFT JOIN rooms r ON r.id = s.room_id WHERE s.deleted_at IS NULL{level_where}",
                *level_params
            ) or 0
            total_rooms = await conn.fetchval(
                f"SELECT COUNT(*) FROM rooms r WHERE r.deleted_at IS NULL{level_where}",
                *level_params
            ) or 0
        else:
            total_students = await conn.fetchval("SELECT COUNT(*) FROM students WHERE deleted_at IS NULL") or 0
            total_rooms = await conn.fetchval("SELECT COUNT(*) FROM rooms WHERE deleted_at IS NULL") or 0

        # 2. top categories (ตามหมวดหลัก+หมวดย่อยใหม่)
        cat_rows = await conn.fetch(
            f"""
            SELECT i.main_category, i.category, COUNT(*) AS cnt
            FROM issues i{issue_join}
            WHERE i.deleted_at IS NULL{level_where}
            GROUP BY i.main_category, i.category
            ORDER BY cnt DESC LIMIT 6
            """,
            *level_params
        )
        top_categories = [
            {
                "main_category": r["main_category"],
                "category": r["category"],
                "label": get_subcategory_label(r["main_category"], r["category"]),
                "count": r["cnt"],
            }
            for r in cat_rows
        ]

        # 3. by status
        status_rows = await conn.fetch(
            f"""
            SELECT i.status, COUNT(*) AS cnt
            FROM issues i{issue_join}
            WHERE i.deleted_at IS NULL{level_where}
            GROUP BY i.status
            """,
            *level_params
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
            day_params = list(level_params) + [day]
            day_clause = f" AND i.created_at::date = ${len(day_params)}"
            cnt = await conn.fetchval(
                f"""
                SELECT COUNT(*) FROM issues i{issue_join}
                WHERE i.deleted_at IS NULL{level_where}{day_clause}
                """,
                *day_params
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
