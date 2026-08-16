import asyncpg
from datetime import datetime, timedelta, timezone

from core.categories import (
    get_main_categories,
    get_main_category_description,
    get_subcategory_label,
)
from core.rbac import get_access_scope, require_permission_anywhere

STATUS_LABELS = {
    "pending": "รอรับเรื่อง",
    "in_progress": "กำลังดำเนินการ",
    "resolved": "แก้ไขเสร็จ",
    "escalated": "ส่งต่อระดับบน",
    "cancelled": "ถูกยกเลิก",
}

# ลำดับสถานะคงที่ (ให้ UI เรียงแน่นอน + เติม 0 ให้ครบ)
STATUS_ORDER = ["pending", "in_progress", "escalated", "resolved", "cancelled"]

# เขตเวลาโรงเรียน (ทุกที่ในระบบ)
BKK = timezone(timedelta(hours=7))


def _status_stats(counts: dict) -> list:
    """แปลง dict {status: count} → list ของทุกสถานะ เรียงตาม STATUS_ORDER (เติม 0 ถ้าไม่มี)"""
    return [
        {"status": st, "label": STATUS_LABELS.get(st, st), "count": int(counts.get(st, 0))}
        for st in STATUS_ORDER
    ]


def _scope_clause(scope: dict) -> tuple:
    """
    สร้าง WHERE clause + params จำกัดขอบเขตข้อมูลสำหรับ dashboard
    - scope='level' (ครูทั่วไป) → เฉพาะห้องที่ระดับชั้นตรงกับ staff_level (เช่น 'ม.4')
    - scope='none' (ครูที่ไม่มีระดับชั้น) → ไม่เห็นข้อมูลใดเลย (กันเห็นทั้งโรงเรียน)
    - scope อื่น (all/super) → ไม่จำกัด (ดูทั้งโรงเรียน)
    """
    if scope["scope"] == "level" and scope.get("level"):
        return " AND r.level = $1", [scope["level"]]
    if scope["scope"] == "none":
        return " AND 1 = 0", []
    return "", []


async def get_dashboard(pool: asyncpg.Pool, user_id: int) -> dict:
    """
    สรุปสถิติ dashboard — กลุ่มตาม 3 หมวดหลัก (suggestion / wellbeing / report)
    - ตรวจสิทธิ์ VIEW_DASHBOARD ผ่าน core.rbac (super admin/is_admin ข้าม)
    - ครูทั่วไป (teacher): เห็นเฉพาะระดับชั้นตัวเอง (staff_level)
    """
    async with pool.acquire() as conn:
        # 1. สิทธิ์ดู dashboard (ข้ามทุกห้อง — teacher ก็มี VIEW_DASHBOARD)
        await require_permission_anywhere(conn, user_id, "VIEW_DASHBOARD")

        # 2. ขอบเขตข้อมูล: super / all / level / none
        scope = await get_access_scope(conn, user_id)
        level_where, level_params = _scope_clause(scope)

        # scope ที่ส่งให้ frontend: 'level' = เฉพาะระดับชั้น, 'none' = ไม่มีระดับ (ครูที่ยังไม่ตั้ง), อื่นๆ = ทั้งโรงเรียน
        if scope["scope"] == "level":
            dashboard_scope = "level"
        elif scope["scope"] == "none":
            dashboard_scope = "none"
        else:
            dashboard_scope = "all"

        # 3. หมวดหลักทั้ง 3 (จาก config/categories.json)
        main_categories = get_main_categories()
        category_codes = list(main_categories.keys())

        # ── 4. นับแยก (หมวดหลัก × สถานะ) — query เดียว ──
        rows = await conn.fetch(
            f"""
            SELECT i.main_category, i.status, COUNT(*) AS cnt
            FROM issues i
            LEFT JOIN rooms r ON r.id = i.room_id
            WHERE i.deleted_at IS NULL{level_where}
            GROUP BY i.main_category, i.status
            """,
            *level_params
        )
        by_main_status: dict = {}
        for r in rows:
            by_main_status.setdefault(r["main_category"], {})[r["status"]] = r["cnt"]

        # ── 5. หมวดย่อย × สถานะ (หมวดหลัก × หมวดย่อย × สถานะ) — query เดียว ──
        cat_status_rows = await conn.fetch(
            f"""
            SELECT i.main_category, i.category, i.status, COUNT(*) AS cnt
            FROM issues i
            LEFT JOIN rooms r ON r.id = i.room_id
            WHERE i.deleted_at IS NULL{level_where}
            GROUP BY i.main_category, i.category, i.status
            """,
            *level_params
        )
        by_cat_status: dict = {}
        for r in cat_status_rows:
            by_cat_status.setdefault(r["main_category"], []).append(r)

        # ── 6. เรื่องล่าสุดต่อหมวดหลัก (5 เรื่อง) — window function 1 query ──
        recent_rows = await conn.fetch(
            f"""
            SELECT * FROM (
                SELECT
                    i.id, i.main_category, i.category, i.title, i.status,
                    i.current_level, i.created_at, r.room_name,
                    ROW_NUMBER() OVER (
                        PARTITION BY i.main_category ORDER BY i.created_at DESC
                    ) AS rn
                FROM issues i
                LEFT JOIN rooms r ON r.id = i.room_id
                WHERE i.deleted_at IS NULL{level_where}
            ) sub
            WHERE sub.rn <= 5
            ORDER BY sub.main_category, sub.created_at DESC
            """,
            *level_params
        )
        recent_by_main: dict = {}
        for r in recent_rows:
            recent_by_main.setdefault(r["main_category"], []).append(r)

        # ── 7. รวมตัวเลขระดับบน (ทุกหมวด) ──
        # 💡 นับจากหมวดหลักที่รู้จักเท่านั้น — กันกรณี main_category อยู่นอก config (เช่นเก่าที่ถูกลบ)
        #    ทำให้ pending+in_progress+... == total_issues และ sum(main_categories[].total) == total_issues เสมอ
        total_by_main = {mc: sum(by_main_status.get(mc, {}).values()) for mc in category_codes}
        total_issues = sum(total_by_main.values())

        by_status_all: dict = {}
        for mc in category_codes:
            for st, cnt in by_main_status.get(mc, {}).items():
                by_status_all[st] = by_status_all.get(st, 0) + cnt
        by_status = _status_stats(by_status_all)

        # ── 8. งานเกินเวลา (รายหมวดหลัก) — กำลังดำเนินการ + countdown ล่าสุดเลยกำหนด ──
        # กลุ่มตาม main_category ให้ sum(overdue รายหมวด) == overdue รวมเสมอ
        overdue_rows = await conn.fetch(
            f"""
            SELECT i.main_category, COUNT(*) AS cnt
            FROM issues i
            LEFT JOIN rooms r ON r.id = i.room_id
            WHERE i.deleted_at IS NULL{level_where}
              AND i.status = 'in_progress'
              AND EXISTS (
                  SELECT 1 FROM issue_countdowns cd
                  WHERE cd.issue_id = i.id
                    AND cd.deadline < NOW()
                    AND cd.id = (
                        SELECT MAX(id) FROM issue_countdowns WHERE issue_id = i.id
                    )
              )
            GROUP BY i.main_category
            """,
            *level_params
        )
        overdue_by_main = {r["main_category"]: r["cnt"] for r in overdue_rows}
        overdue = sum(overdue_by_main.get(mc, 0) for mc in category_codes)

        # ── 9. จำนวนนักเรียน / ห้อง (ตาม scope) ──
        total_students, total_rooms = await _count_people(conn, scope)

        # ── 10. แนวโน้ม 7 วัน (เทียบวันตาม Asia/Bangkok) ──
        trend = await _trend_7days(conn, level_where, level_params)

        # ── 11. การเข้าใช้งาน (audit_logs) — เฉพาะผู้ที่เห็นทั้งโรงเรียน ──
        # (ครูระดับชั้นไม่ควรเห็นว่าใครเข้าระบบบ้างทั้งโรงเรียน — ข้อมูลส่วนบุคคลข้ามระดับ)
        if dashboard_scope == "all":
            usage_count, recent_logins = await _usage(conn)
        else:
            usage_count, recent_logins = 0, []

        # ── 12. ประกอบผลลัพธ์ group ตาม 3 หมวดหลัก ──
        main_dashboards = []
        for code in category_codes:
            info = main_categories.get(code, {})
            sub_labels = info.get("subcategories", {})        # {code: label}
            sub_details = info.get("subcategory_details", {})  # {code: description}

            # รวมตัวเลขรายหมวดย่อยจาก (หมวดย่อย × สถานะ) — ใช้ config เป็นแกน
            # ให้ sum(subcategories[].count) == total เสมอ (บทเรียน: นับจาก key set เดียวกัน)
            # หมวดย่อยที่ไม่อยู่ใน config (หมวดเก่า/insert ตรง) → รวมเข้า "อื่นๆ" (ไม่ทิ้งข้อมูล)
            sub_counts: dict = {}
            sub_status: dict = {}
            other_count = 0
            other_status: dict = {}
            for r in by_cat_status.get(code, []):
                c = r["category"]
                if c in sub_labels:
                    sub_counts[c] = sub_counts.get(c, 0) + r["cnt"]
                    # ⚠️ อย่าห่อใส่ assignment เดียว: Python คำนวณ RHS ก่อน target
                    # (sub_status[c] จะ KeyError ถ้ายังไม่มี key) — แยกเป็น 2 บรรทัด
                    st = sub_status.setdefault(c, {})
                    st[r["status"]] = st.get(r["status"], 0) + r["cnt"]
                else:
                    other_count += r["cnt"]
                    other_status[r["status"]] = other_status.get(r["status"], 0) + r["cnt"]

            # รายการหมวดย่อย (เรียง count มากไปน้อย — อันเยอะสุดอยู่บน; เสมอ → เรียงตาม config)
            sub_items = [
                {"category": c, "label": sub_labels[c],
                 "description": sub_details.get(c, ""),
                 "count": sub_counts.get(c, 0), "by_status": sub_status.get(c, {})}
                for c in sub_labels
            ]
            sub_items.sort(key=lambda x: x["count"], reverse=True)
            # "อื่นๆ" ต่อท้ายเสมอ (ไม่ไปแทรกกลาง leaderboard — เป็นหมวดตกค้าง ไม่ใช่หมวดจริง)
            if other_count > 0:
                sub_items.append({
                    "category": "_other", "label": "อื่นๆ",
                    "description": "หมวดย่อยที่ไม่อยู่ในระบบปัจจุบัน",
                    "count": other_count, "by_status": other_status,
                })
            subcategories = [
                {
                    "category": it["category"], "label": it["label"],
                    "description": it["description"], "count": it["count"],
                    "by_status": _status_stats(it["by_status"]),
                }
                for it in sub_items
            ]

            # เรื่องล่าสุดในหมวด (สำหรับคลิกเข้าไปติดตาม)
            recent_issues = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "main_category": code,
                    "category": r["category"],
                    "category_label": get_subcategory_label(code, r["category"]),
                    "status": r["status"],
                    "current_level": r["current_level"],
                    "room_name": r["room_name"],
                    "created_at": r["created_at"],
                }
                for r in recent_by_main.get(code, [])
            ]

            main_dashboards.append({
                "code": code,
                "label": info.get("label", code),
                "description": get_main_category_description(code),
                "total": total_by_main.get(code, 0),
                "overdue": overdue_by_main.get(code, 0),
                "by_status": _status_stats(by_main_status.get(code, {})),
                "subcategories": subcategories,
                "recent_issues": recent_issues,
            })

    return {
        "scope": dashboard_scope,
        "scope_label": scope.get("level") if dashboard_scope == "level" else None,
        "total_issues": total_issues,
        "pending": by_status_all.get("pending", 0),
        "in_progress": by_status_all.get("in_progress", 0),
        "resolved": by_status_all.get("resolved", 0),
        "escalated": by_status_all.get("escalated", 0),
        "cancelled": by_status_all.get("cancelled", 0),
        "overdue": overdue,
        "total_students": total_students,
        "total_rooms": total_rooms,
        "by_status": by_status,
        "main_categories": main_dashboards,
        "trend": trend,
        "usage_count": usage_count,
        "recent_logins": recent_logins,
    }


async def _count_people(conn: asyncpg.Connection, scope: dict) -> tuple:
    """จำนวนนักเรียน/ห้อง — ครูทั่วไปนับเฉพาะระดับชั้นตัวเอง, ครูที่ไม่มีระดับชั้น = 0"""
    if scope["scope"] == "none":
        # ครูที่ยังไม่มี staff_level → ไม่เห็นจำนวนนักเรียน/ห้องเลย (กันเห็นทั้งโรงเรียน)
        return 0, 0
    if scope["scope"] == "level" and scope.get("level"):
        level = scope["level"]
        total_students = await conn.fetchval(
            """
            SELECT COUNT(*) FROM students s
            LEFT JOIN rooms r ON r.id = s.room_id
            WHERE s.deleted_at IS NULL AND r.level = $1
            """,
            level
        ) or 0
        total_rooms = await conn.fetchval(
            "SELECT COUNT(*) FROM rooms r WHERE r.deleted_at IS NULL AND r.level = $1",
            level
        ) or 0
    else:
        total_students = await conn.fetchval(
            "SELECT COUNT(*) FROM students WHERE deleted_at IS NULL"
        ) or 0
        total_rooms = await conn.fetchval(
            "SELECT COUNT(*) FROM rooms WHERE deleted_at IS NULL"
        ) or 0
    return total_students, total_rooms


async def _trend_7days(conn: asyncpg.Connection, level_where: str, level_params: list) -> list:
    """แนวโน้ม 7 วันย้อนหลัง (นับวันตาม Asia/Bangkok) — 1 query แล้วเติมวันที่ที่ไม่มีเรื่อง"""
    today = datetime.now(timezone.utc).astimezone(BKK).date()

    # ระบุ placeholder ของวันที่ให้ต่อจาก level_params (บทเรียน: นับ $n ให้ครบ — อย่าเริ่ม $1 ซ้ำ)
    date_param = len(level_params) + 1
    rows = await conn.fetch(
        f"""
        SELECT (i.created_at AT TIME ZONE 'Asia/Bangkok')::date AS day, COUNT(*) AS cnt
        FROM issues i
        LEFT JOIN rooms r ON r.id = i.room_id
        WHERE i.deleted_at IS NULL{level_where}
          AND (i.created_at AT TIME ZONE 'Asia/Bangkok')::date >= ${date_param}
        GROUP BY day
        """,
        *level_params, today - timedelta(days=6)
    )
    counts = {r["day"]: r["cnt"] for r in rows}

    trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        trend.append({"date": day.isoformat(), "count": counts.get(day, 0)})
    return trend


async def _usage(conn: asyncpg.Connection) -> tuple:
    """จำนวนการเข้าใช้งาน + ผู้เข้าใช้ล่าสุด (จาก audit_logs — ถ้ายังไม่มีข้อมูลให้เป็น 0)"""
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
        pass  # audit_logs อาจยังไม่มีข้อมูล
    return usage_count, recent_logins
