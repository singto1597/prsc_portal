"""
PIRI Boards — Phase 5: Board Moderation & Reports (PIRI Talk)
=============================================================
- report_comment    — นักเรียนทุกคนแจ้งความไม่เหมาะสมของคอมเมนต์ (รอสภา/แอดมินจัดการ)
- hide_comment      — สภา/แอดมินซ่อนคอมเมนต์ + ลูกหลานทั้งหมด (subtree) → ลด comment_count
- unhide_comment    — กลับมาแสดง (subtree) → เพิ่ม comment_count คืน
- hide_board        — ซ่อน board ทั้งบอร์ด (หลุดจาก feed/detail)
- unhide_board      — กลับมาแสดง
- list_reports      — คิวรายงาน (สภา/แอดมิน) กรอง status/reason/ค้นหา + แบ่งหน้า
- resolve_report    — จัดการรายงาน: action='hide' (ซ่อนคอมเมนต์) / 'dismiss' (ปัดตก ไม่ซ่อน)

🔧 Counter management (ตามคำสั่ง): ทุกการซ่อน/แสดงคอมเมนต์ ต้อง +- comment_count
ที่ตารางหลัก piri_boards ให้ตรงกับคอมเมนต์ที่ยังแสดงอยู่จริงเสมอ

กฎ backend.md: ทุก write → AuditLogger ใน transaction เดียว, SQL parameterized,
อำนาจระดับสภา/แอดมินเช็คผ่าน _has_council_authority (เหมือน approve_to_public)
"""
from typing import Optional
import asyncpg

from core.exceptions import NotFoundError, ForbiddenError, ValidationError, ConflictError
from services.issue_service import _has_council_authority
from services.board_service import _display_name
from models.board_schemas import REPORT_REASONS

# 🔔 Notification writer (อยู่ใน transaction เดียวกับข้อมูลหลัก — ลอกแบบ AuditLogger)
from services.notification_service import notify, notify_bulk, _council_ids, _user_display_name

# ค่าคงที่หมวดเหตุผล — sync กับ schemas (piri_board_reports.reason CHECK)
REPORT_REASON_LABELS = {
    "bullying": "กลั่นแกล้ง/คุกคาม",
    "profanity": "คำหยาบคาย",
    "spam": "สแปม/โฆษณา",
    "privacy": "เปิดเผยข้อมูลส่วนตัว",
    "other": "อื่นๆ",
}

MAX_REPORT_DETAIL = 500
# 🛡️ กัน flood คิวรายงาน: user 1 คนแจ้งแบบ open ค้างไว้ได้ไม่เกินเท่านี้ (รอสภา/แอดมินจัดการก่อน)
MAX_OPEN_REPORTS_PER_USER = 10
# กัน TOCTOU (reply ถูก insert คั่นระหว่างนับ subtree กับซ่อน): re-walk subtree สูงสุดกี่รอบ
MAX_HIDE_PASSES = 3


async def _require_council_authority(conn, user_id: int) -> None:
    """อำนาจระดับสภา/แอดมิน (จัดการบอร์ดสาธารณะ/รายงานได้) — เหมือน approve_to_public"""
    if not await _has_council_authority(conn, user_id):
        raise ForbiddenError("เฉพาะสภานักเรียน/ประธานสภา/ครูสภา/แอดมินที่จัดการบอร์ดสาธารณะได้")


async def _subtree_ids(conn, root_id: int) -> list:
    """id ของคอมเมนต์ + ลูกหลานทั้งหมด (walk ผ่าน parent_comment_id — เฉพาะที่ยังไม่ soft-delete)
    ใช้ทั้ง hide/unhide subtree + resolve รายงานทั้งต้น"""
    return await conn.fetchval(
        """
        WITH RECURSIVE sub(cid) AS (
            SELECT $1::integer
            UNION ALL
            SELECT c.id
            FROM piri_board_comments c
            JOIN sub ON c.parent_comment_id = sub.cid
            WHERE c.deleted_at IS NULL
        )
        SELECT COALESCE(ARRAY_AGG(cid), '{}'::int[]) FROM sub
        """,
        root_id
    ) or []


async def _resolve_open_reports(conn, comment_ids: list, moderator_id: int, note: str) -> None:
    """ปิดรายงาน open ทั้งหมดของคอมเมนต์ชุดนี้ (หลังซ่อนแล้ว) → status='resolved'"""
    if not comment_ids:
        return
    await conn.execute(
        """
        UPDATE piri_board_reports
        SET status = 'resolved', resolved_by = $2, resolved_at = NOW(),
            resolution_note = $3, updated_at = NOW()
        WHERE comment_id = ANY($1::int[]) AND status = 'open' AND deleted_at IS NULL
        """,
        comment_ids, moderator_id, note
    )


async def _hide_comment_subtree(conn, board_id: int, root_id: int, moderator_id: int, reason: str) -> int:
    """
    ซ่อนคอมเมนต์ + ลูกหลานทั้งหมด (subtree) แล้วจัดการให้ครบใน transaction เดียว:
    1. ตั้ง is_hidden_by_admin=TRUE ทั้งต้น (เฉพาะที่ยังไม่ซ่อน → นับจำนวนที่เปลี่ยนจริง)
    2. ลด piri_boards.comment_count ตามจำนวนที่ซ่อนจริง (GREATEST กันติดลบ)
    3. ปิดรายงาน open ทั้งหมดของคอมเมนต์ใน subtree (จัดการแล้ว)
    คืนจำนวนคอมเมนต์ที่ซ่อนใหม่ (0 = ซ่อนอยู่แล้ว → เรียกแล้วไม่พัง counter)
    """
    ids = await _subtree_ids(conn, root_id)
    if not ids:
        return 0
    hidden_count = await conn.fetchval(
        """
        WITH updated AS (
            UPDATE piri_board_comments
            SET is_hidden_by_admin = TRUE, hidden_reason = $2, hidden_by = $3, updated_at = NOW()
            WHERE id = ANY($1::int[]) AND is_hidden_by_admin = FALSE
            RETURNING id
        )
        SELECT COUNT(*) FROM updated
        """,
        ids, reason, moderator_id
    )
    # ⚠️ TOCTOU: reply ถูก insert คั่นระหว่างนับ subtree กับซ่อน (parent ยัง visible ตอน insert)
    # → re-walk subtree แล้วซ่อนให้ครบ (สูงสุด MAX_HIDE_PASSES รอบ; กัน reply หลุดใต้ parent ที่ซ่อนแล้ว)
    total_hidden = hidden_count
    for _ in range(MAX_HIDE_PASSES - 1):
        ids = await _subtree_ids(conn, root_id)
        if not ids:
            break
        n = await conn.fetchval(
            """
            WITH updated AS (
                UPDATE piri_board_comments
                SET is_hidden_by_admin = TRUE, hidden_reason = $2, hidden_by = $3, updated_at = NOW()
                WHERE id = ANY($1::int[]) AND is_hidden_by_admin = FALSE
                RETURNING id
            )
            SELECT COUNT(*) FROM updated
            """,
            ids, reason, moderator_id
        )
        if n == 0:
            break
        total_hidden += n

    if total_hidden > 0:
        await conn.execute(
            """
            UPDATE piri_boards
            SET comment_count = GREATEST(comment_count - $2, 0), updated_at = NOW()
            WHERE id = $1
            """,
            board_id, total_hidden
        )
    # ปิดรายงาน open ทั้งหมดของคอมเมนต์ใน subtree (ปัจจุบัน — รวมที่เพิ่งซ่อนรอบหลัง)
    await _resolve_open_reports(conn, await _subtree_ids(conn, root_id), moderator_id, reason)
    return total_hidden


async def _unhide_comment(conn, board_id: int, comment_id: int) -> int:
    """กลับมาแสดงคอมเมนต์เดียว (ไม่ใช่ subtree) → เพิ่ม comment_count คืน 1
    ⚠️ ตั้งใจ unhide เฉพาะตัวเดียว: unhide subtree จะเผลอฟื้นคอมเมนต์ที่ถูกซ่อนแยกคนละครั้ง
    (resurrection bug — adversarial review จับ: คอมเมนต์ที่แอดมินซ่อนเองกลับมาโผล่ทั้งโรงเรียน)
    → คนที่ต้องการคืนทั้งต้น unhide ทีละตัว (เด็ดขาด predictable กันคืนของที่ไม่ได้ตั้งใจ)"""
    unhidden = await conn.fetchval(
        """
        UPDATE piri_board_comments
        SET is_hidden_by_admin = FALSE, updated_at = NOW()
        WHERE id = $1 AND board_id = $2 AND is_hidden_by_admin = TRUE AND deleted_at IS NULL
        RETURNING id
        """,
        comment_id, board_id
    )
    if unhidden is None:
        return 0
    await conn.execute(
        """
        UPDATE piri_boards
        SET comment_count = comment_count + 1, updated_at = NOW()
        WHERE id = $1
        """,
        board_id
    )
    return 1


# ============================================================
# 🚩 1) report_comment — นักเรียนแจ้งความไม่เหมาะสม
# ============================================================
async def report_comment(
    pool: asyncpg.Pool,
    user_id: int,
    board_id: int,
    comment_id: int,
    *,
    reason: str,
    detail: Optional[str] = None,
) -> dict:
    """
    แจ้งความไม่เหมาะสมของคอมเมนต์ (PIRI Talk):
    - board ต้อง active + คอมเมนต์ต้องอยู่ใน board (คอมเมนต์ที่ซ่อนแล้วแจ้งได้ — บันทึกไว้ดู)
    - แจ้งคอมเมนต์ของตัวเองไม่ได้ (ValidationError 400)
    - แจ้งซ้ำ (คนเดิม คอมเมนต์เดิม ยัง active) → UniqueViolationError → ConflictError 409
    - AuditLogger(action="REPORT_COMMENT") ใน transaction เดียว
    """
    if reason not in REPORT_REASONS:
        raise ValidationError(f"เหตุผลการแจ้งไม่ถูกต้อง: {reason} (ต้องเป็นหนึ่งใน {', '.join(REPORT_REASONS)})")
    if detail and len(detail) > MAX_REPORT_DETAIL:
        raise ValidationError(f"รายละเอียดยาวเกิน {MAX_REPORT_DETAIL} ตัวอักษร")

    async with pool.acquire() as conn:
        async with conn.transaction():
            board = await conn.fetchrow(
                "SELECT * FROM piri_boards WHERE id = $1 AND deleted_at IS NULL AND status = 'active'",
                board_id
            )
            if not board:
                raise NotFoundError("ไม่พบ board นี้")

            comment = await conn.fetchrow(
                """
                SELECT * FROM piri_board_comments
                WHERE id = $1 AND board_id = $2 AND deleted_at IS NULL
                """,
                comment_id, board_id
            )
            if not comment:
                raise NotFoundError("ไม่พบคอมเมนต์นี้")
            if comment["user_id"] == user_id:
                raise ValidationError("ไม่สามารถแจ้งความไม่เหมาะสมของคอมเมนต์ตัวเองได้")

            # 🛡️ กัน flood คิว: user แจ้งแบบ open ค้างไว้เกิน MAX_OPEN_REPORTS_PER_USER ไม่ได้
            # (adversarial review: ไม่มี cap → สุ่ม enumerate board/comment ใส่รายงานนับพันฝังคิวสภา)
            open_count = await conn.fetchval(
                "SELECT COUNT(*) FROM piri_board_reports WHERE reporter_id = $1 AND status = 'open' AND deleted_at IS NULL",
                user_id
            )
            if open_count >= MAX_OPEN_REPORTS_PER_USER:
                raise ValidationError(
                    f"แจ้งได้ไม่เกิน {MAX_OPEN_REPORTS_PER_USER} รายการค้างอยู่ รอสภานักเรียนจัดการก่อน"
                )

            try:
                report_id = await conn.fetchval(
                    """
                    INSERT INTO piri_board_reports (board_id, comment_id, reporter_id, reason, detail)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    board_id, comment_id, user_id, reason, detail
                )
            except asyncpg.exceptions.UniqueViolationError:
                # UNIQUE(reporter_id, comment_id) WHERE deleted_at IS NULL — แจ้งซ้ำ
                raise ConflictError("คุณแจ้งคอมเมนต์นี้ไปแล้ว รอสภานักเรียนจัดการ")

            # 🛡️ Audit log (ภายใน transaction เดียว — ตามกฎ backend.md)
            from core.logger import AuditLogger
            await AuditLogger("board_moderation_service").log(
                conn=conn, action="REPORT_COMMENT",
                actor_identifier=str(user_id), client_source="web",
                user_id=user_id,
                entity_type="piri_board_report", entity_id=report_id,
                new_values={
                    "board_id": board_id, "comment_id": comment_id,
                    "reason": reason, "detail": detail,
                },
            )

            # 🔔 แจ้งสภา/แอดมินว่ามีรายงานใหม่ (badge "จัดการรายงาน" — exclude ผู้แจ้งเอง)
            reason_label = REPORT_REASON_LABELS.get(reason, reason)
            await notify_bulk(
                conn, await _council_ids(conn),
                group_type="report", type="report_new",
                title="มีรายงานใหม่รอจัดการ",
                body=f'รายงาน "{reason_label}" ในกระทู้ "{board["title"]}"',
                entity_type="piri_board_report", entity_id=report_id,
                board_id=board_id,
                actor_id=user_id,
            )

    return {"id": report_id, "board_id": board_id, "comment_id": comment_id, "status": "open"}


# ============================================================
# 🛡️ 2) hide_comment / unhide_comment — moderation (subtree + counter)
# ============================================================
async def hide_comment(
    pool: asyncpg.Pool,
    moderator_id: int,
    board_id: int,
    comment_id: int,
    *,
    reason: str,
) -> dict:
    """ซ่อนคอมเมนต์ + ลูกหลาน (subtree) — ลด comment_count ตามจำนวนที่ซ่อนจริง"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _require_council_authority(conn, moderator_id)

            comment = await conn.fetchrow(
                """
                SELECT * FROM piri_board_comments
                WHERE id = $1 AND board_id = $2 AND deleted_at IS NULL
                """,
                comment_id, board_id
            )
            if not comment:
                raise NotFoundError("ไม่พบคอมเมนต์นี้")
            if comment["is_hidden_by_admin"]:
                raise ConflictError("คอมเมนต์นี้ถูกซ่อนอยู่แล้ว")

            hidden_count = await _hide_comment_subtree(conn, board_id, comment_id, moderator_id, reason)

            # 🛡️ Audit log (ภายใน transaction เดียว — ตามกฎ backend.md)
            from core.logger import AuditLogger
            await AuditLogger("board_moderation_service").log(
                conn=conn, action="HIDE_COMMENT",
                actor_identifier=str(moderator_id), client_source="web",
                user_id=moderator_id,
                entity_type="piri_board_comment", entity_id=comment_id,
                old_values={"is_hidden_by_admin": False, "body": comment["body"]},
                new_values={
                    "is_hidden_by_admin": True, "hidden_reason": reason,
                    "board_id": board_id, "hidden_comment_ids_count": hidden_count,
                },
            )

    return {"status": "hidden", "board_id": board_id, "comment_id": comment_id, "hidden_count": hidden_count}


async def unhide_comment(
    pool: asyncpg.Pool,
    moderator_id: int,
    board_id: int,
    comment_id: int,
) -> dict:
    """กลับมาแสดงคอมเมนต์เดียว — เพิ่ม comment_count คืน 1
    (ไม่ใช่ subtree — กัน resurrection bug: อย่าฟื้นคอมเมนต์ที่ถูกซ่อนแยกคนละครั้ง)"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _require_council_authority(conn, moderator_id)

            comment = await conn.fetchrow(
                """
                SELECT * FROM piri_board_comments
                WHERE id = $1 AND board_id = $2 AND deleted_at IS NULL
                """,
                comment_id, board_id
            )
            if not comment:
                raise NotFoundError("ไม่พบคอมเมนต์นี้")
            if not comment["is_hidden_by_admin"]:
                raise ConflictError("คอมเมนต์นี้ไม่ได้ถูกซ่อนอยู่")

            unhidden_count = await _unhide_comment(conn, board_id, comment_id)
            if unhidden_count == 0:
                raise ConflictError("คอมเมนต์นี้ไม่ได้ถูกซ่อนอยู่")

            # 🛡️ Audit log (ภายใน transaction เดียว — ตามกฎ backend.md)
            from core.logger import AuditLogger
            await AuditLogger("board_moderation_service").log(
                conn=conn, action="UNHIDE_COMMENT",
                actor_identifier=str(moderator_id), client_source="web",
                user_id=moderator_id,
                entity_type="piri_board_comment", entity_id=comment_id,
                old_values={"is_hidden_by_admin": True},
                new_values={"is_hidden_by_admin": False, "board_id": board_id, "unhidden_count": unhidden_count},
            )

    return {"status": "active", "board_id": board_id, "comment_id": comment_id, "unhidden_count": unhidden_count}


# ============================================================
# 📦 3) hide_board / unhide_board — ซ่อน board ทั้งบอร์ด
# ============================================================
async def hide_board(
    pool: asyncpg.Pool,
    moderator_id: int,
    board_id: int,
    *,
    reason: str,
) -> dict:
    """ซ่อน board (status='hidden') → หลุดจาก feed + detail 404 (ไม่มีข้อมูลรั่ว)"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _require_council_authority(conn, moderator_id)

            board = await conn.fetchrow(
                "SELECT * FROM piri_boards WHERE id = $1 AND deleted_at IS NULL",
                board_id
            )
            if not board:
                raise NotFoundError("ไม่พบ board นี้")
            if board["status"] == "hidden":
                raise ConflictError("board นี้ถูกซ่อนอยู่แล้ว")

            await conn.execute(
                """
                UPDATE piri_boards
                SET status = 'hidden', closed_by = $2, close_reason = $3, closed_at = NOW(), updated_at = NOW()
                WHERE id = $1
                """,
                board_id, moderator_id, reason
            )

            # ปิดรายงาน open ทั้งหมดของบอร์ดนี้ (บอร์ดถูกซ่อนแล้ว → ไม่มีอะไรให้จัดการต่อ;
            # กันคิวยังโชว์เนื้อหาบอร์ดที่ซ่อนเป็น 'open' — adversarial review จับ)
            await conn.execute(
                """
                UPDATE piri_board_reports
                SET status = 'resolved', resolved_by = $2, resolved_at = NOW(),
                    resolution_note = $3, updated_at = NOW()
                WHERE board_id = $1 AND status = 'open' AND deleted_at IS NULL
                """,
                board_id, moderator_id, f"ซ่อนบอร์ด: {reason}"
            )

            # 🛡️ Audit log (ภายใน transaction เดียว — ตามกฎ backend.md)
            from core.logger import AuditLogger
            await AuditLogger("board_moderation_service").log(
                conn=conn, action="HIDE_BOARD",
                actor_identifier=str(moderator_id), client_source="web",
                user_id=moderator_id,
                entity_type="piri_board", entity_id=board_id,
                old_values={"status": board["status"]},
                new_values={"status": "hidden", "reason": reason},
            )

            # 🔔 แจ้งเจ้าของบอร์ดว่าบอร์ดถูกซ่อน
            if board["author_id"]:
                await notify(
                    conn, user_id=board["author_id"],
                    group_type="board", type="board_hidden",
                    title="กระทู้ของคุณถูกซ่อน",
                    body=f'กระทู้ "{board["title"]}" ถูกซ่อน (เหตุผล: {reason})',
                    entity_type="piri_board", entity_id=board_id, board_id=board_id,
                    actor_id=moderator_id,
                )

    return {"status": "hidden", "board_id": board_id}


async def unhide_board(
    pool: asyncpg.Pool,
    moderator_id: int,
    board_id: int,
) -> dict:
    """กลับมาแสดง board (status='active')"""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await _require_council_authority(conn, moderator_id)

            board = await conn.fetchrow(
                "SELECT * FROM piri_boards WHERE id = $1 AND deleted_at IS NULL",
                board_id
            )
            if not board:
                raise NotFoundError("ไม่พบ board นี้")
            if board["status"] != "hidden":
                raise ConflictError("board นี้ไม่ได้ถูกซ่อนอยู่")

            await conn.execute(
                """
                UPDATE piri_boards
                SET status = 'active', updated_at = NOW()
                WHERE id = $1
                """,
                board_id
            )

            # 🛡️ Audit log (ภายใน transaction เดียว — ตามกฎ backend.md)
            from core.logger import AuditLogger
            await AuditLogger("board_moderation_service").log(
                conn=conn, action="UNHIDE_BOARD",
                actor_identifier=str(moderator_id), client_source="web",
                user_id=moderator_id,
                entity_type="piri_board", entity_id=board_id,
                old_values={"status": "hidden"},
                new_values={"status": "active"},
            )

    return {"status": "active", "board_id": board_id}


# ============================================================
# 📋 4) list_reports — คิวรายงาน (สภา/แอดมิน)
# ============================================================
async def list_reports(
    pool: asyncpg.Pool,
    user_id: int,
    *,
    status: Optional[str] = None,
    reason: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """รายการรายงาน (แบ่งหน้า) — เฉพาะสภา/แอดมิน
    กรอง: status (open/resolved/dismissed), reason (หมวดเหตุผล), q (ค้นหา board title/comment body)"""
    async with pool.acquire() as conn:
        await _require_council_authority(conn, user_id)

        where = ["r.deleted_at IS NULL"]
        params: list = []
        if status:
            params.append(status)
            where.append(f"r.status = ${len(params)}")
        if reason:
            params.append(reason)
            where.append(f"r.reason = ${len(params)}")
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
            where.append(f"(b.title ILIKE ${len(params)} ESCAPE '\\' OR c.body ILIKE ${len(params)} ESCAPE '\\')")
        where_sql = " AND ".join(where)

        rows = await conn.fetch(
            f"""
            SELECT r.*, b.title AS board_title, c.body AS comment_body,
                   u_rep.full_name AS author_full_name,
                   s_rep.prefix, s_rep.first_name, s_rep.last_name,
                   COUNT(*) OVER() AS total_count
            FROM piri_board_reports r
            JOIN piri_boards b ON b.id = r.board_id
            JOIN piri_board_comments c ON c.id = r.comment_id
            LEFT JOIN users u_rep ON u_rep.id = r.reporter_id
            LEFT JOIN students s_rep
                ON s_rep.user_id = r.reporter_id AND s_rep.deleted_at IS NULL AND s_rep.status = 'active'
            WHERE {where_sql}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """,
            *params, limit, offset
        )

        if rows:
            total = rows[0]["total_count"]
        else:
            # ⚠️ ต้อง JOIN b/c ด้วย — where_sql อ้าง b.title/c.body (ลืมตอนแรก → q ที่ไม่เจออะไร
            # 500 missing FROM-clause entry — adversarial review จับได้)
            total = await conn.fetchval(
                f"""
                SELECT COUNT(*)
                FROM piri_board_reports r
                JOIN piri_boards b ON b.id = r.board_id
                JOIN piri_board_comments c ON c.id = r.comment_id
                WHERE {where_sql}
                """,
                *params
            ) or 0

    return {
        "items": [_report_to_dict(r) for r in rows],
        "total": total,
        "page": offset // limit + 1,
        "page_size": limit,
        "pages": (total + limit - 1) // limit if total else 0,
    }


def _report_to_dict(row) -> dict:
    """แถวรายงาน (หลัง JOIN board/comment/user) → dict สำหรับ response"""
    return {
        "id": row["id"],
        "board_id": row["board_id"],
        "board_title": row["board_title"],
        "comment_id": row["comment_id"],
        "comment_body": row["comment_body"],
        "reporter_id": row["reporter_id"],
        "reporter_name": _display_name(row),
        "reason": row["reason"],
        "detail": row["detail"],
        "status": row["status"],
        "resolved_by": row["resolved_by"],
        "resolved_at": row["resolved_at"],
        "resolution_note": row["resolution_note"],
        "created_at": row["created_at"],
    }


# ============================================================
# ✅ 5) resolve_report — สภา/แอดมินจัดการรายงาน
# ============================================================
async def resolve_report(
    pool: asyncpg.Pool,
    moderator_id: int,
    report_id: int,
    *,
    action: str,
    note: Optional[str] = None,
) -> dict:
    """จัดการรายงาน:
    - action='hide'    → ซ่อนคอมเมนต์ (subtree + ลด counter) + ปิดรายงาน open ทั้งหมดที่จุดนั้น
    - action='dismiss' → ปัดตก (ไม่ซ่อน) — ปิดรายงานนี้รายการเดียว
    รายงานที่ปิดแล้วจัดการซ้ำไม่ได้ (ConflictError 409)
    """
    if action not in ("hide", "dismiss"):
        raise ValidationError(f"การจัดการไม่ถูกต้อง: {action} (ต้องเป็น hide/dismiss)")

    async with pool.acquire() as conn:
        async with conn.transaction():
            await _require_council_authority(conn, moderator_id)

            report = await conn.fetchrow(
                "SELECT * FROM piri_board_reports WHERE id = $1 AND deleted_at IS NULL",
                report_id
            )
            if not report:
                raise NotFoundError("ไม่พบรายงานนี้")
            if report["status"] != "open":
                raise ConflictError("รายงานนี้ถูกจัดการไปแล้ว")

            if action == "hide":
                reason = note or "ซ่อนคอมเมนต์ตามรายงาน"
                hidden_count = await _hide_comment_subtree(
                    conn, report["board_id"], report["comment_id"], moderator_id, reason
                )
                resolved = {"action": "hide", "hidden_count": hidden_count}
            else:  # dismiss
                await conn.execute(
                    """
                    UPDATE piri_board_reports
                    SET status = 'dismissed', resolved_by = $2, resolved_at = NOW(),
                        resolution_note = $3, updated_at = NOW()
                    WHERE id = $1
                    """,
                    report_id, moderator_id, note
                )
                resolved = {"action": "dismiss", "hidden_count": 0}

            # 🛡️ Audit log (ภายใน transaction เดียว — ตามกฎ backend.md)
            from core.logger import AuditLogger
            await AuditLogger("board_moderation_service").log(
                conn=conn, action="RESOLVE_REPORT",
                actor_identifier=str(moderator_id), client_source="web",
                user_id=moderator_id,
                entity_type="piri_board_report", entity_id=report_id,
                old_values={"status": "open", "reason": report["reason"]},
                new_values={"status": "resolved" if action == "hide" else "dismissed", "note": note, **resolved},
            )

            # 🔔 แจ้งผู้แจ้งรายงานว่าจัดการแล้ว
            if report["reporter_id"]:
                board_title = await conn.fetchval(
                    "SELECT title FROM piri_boards WHERE id = $1", report["board_id"]
                ) or f"บอร์ด #{report['board_id']}"
                action_label = "ซ่อนคอมเมนต์แล้ว" if action == "hide" else "ปัดตก (ไม่ซ่อน)"
                actor_display = await _user_display_name(conn, moderator_id) or "สภานักเรียน"
                await notify(
                    conn, user_id=report["reporter_id"],
                    group_type="report", type="report_actioned",
                    title="รายงานของคุณถูกจัดการแล้ว",
                    body=f'รายงานในกระทู้ "{board_title}" ถูกจัดการโดย {actor_display} ({action_label})',
                    entity_type="piri_board_report", entity_id=report_id,
                    board_id=report["board_id"],
                    actor_id=moderator_id, actor_name=actor_display,
                )

    return {
        "report_id": report_id,
        "status": "resolved" if action == "hide" else "dismissed",
        **resolved,
    }
