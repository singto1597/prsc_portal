from fastapi import APIRouter, Depends, HTTPException, Query, Request
import asyncpg

from core.dependencies import get_db_pool, get_current_user
from core.exceptions import NotFoundError, ForbiddenError, ValidationError, ConflictError
from models.board_schemas import (
    VoteSubmitRequest, CommentCreateRequest, VoteResultOut,
    BoardSummaryOut, BoardDetailOut, BoardCommentOut, BoardListOut,
)
from services import board_service
from services import audit_service

router = APIRouter(prefix="/boards", tags=["PIRI Boards"])


def _ensure_user(user_ctx: dict) -> int:
    """ดึง user_id หรือ raise 401"""
    uid = user_ctx.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")
    return uid


def _err(e: Exception):
    """แปลง domain exception → HTTPException (pattern เดียวกับ issue_router)"""
    if isinstance(e, NotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ForbiddenError):
        return HTTPException(status_code=403, detail=str(e))
    if isinstance(e, ValidationError):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, ConflictError):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {e}")


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ===================== feed board =====================
@router.get("", response_model=BoardListOut)
async def list_public_boards(
    board_type: str | None = Query(None, pattern="^(vote|talk)$", description="กรองตามประเภท: vote/talk"),
    q: str | None = Query(None, max_length=100, description="ค้นหา: ชื่อ/รายละเอียด board"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """📋 feed board สาธารณะ (active เท่านั้น) — ทุกคนที่ล็อกอินเห็นได้ (ไม่ต้องเช็คระดับ)"""
    uid = _ensure_user(user_ctx)
    result = await board_service.list_public_boards(
        pool, board_type=board_type, q=q, limit=limit, offset=offset
    )
    # 🛡️ Audit: เปิด feed (best-effort)
    await audit_service.log_read(pool, uid, "READ_PUBLIC_BOARDS", "piri_board", endpoint="GET /api/boards")
    return BoardListOut(
        items=[BoardSummaryOut(**b) for b in result["items"]],
        total=result["total"], page=result["page"],
        page_size=result["page_size"], pages=result["pages"],
    )


@router.get("/{board_id}", response_model=BoardDetailOut)
async def get_board_detail(
    board_id: int,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """🔍 รายละเอียด board: vote → choices + my_vote; talk → comments (threaded)"""
    uid = _ensure_user(user_ctx)
    try:
        detail = await board_service.get_board_detail(pool, uid, board_id)
    except NotFoundError as e:
        raise _err(e)
    # 🛡️ Audit: ดู board (best-effort)
    await audit_service.log_read(
        pool, uid, "READ_BOARD", "piri_board", entity_id=board_id,
        endpoint=f"GET /api/boards/{board_id}",
    )
    return BoardDetailOut(**detail)


# ===================== โหวต (PIRI Vote) =====================
@router.post("/{board_id}/vote", response_model=VoteResultOut)
async def submit_vote(
    board_id: int,
    req: VoteSubmitRequest,
    request: Request,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """🗳️ โหวต board แบบ vote — 1 เสียงต่อ board (โหวตซ้ำ → 409)"""
    uid = _ensure_user(user_ctx)
    try:
        result = await board_service.submit_vote(
            pool, uid, board_id, req.choice_id,
            ip=_client_ip(request), user_agent=request.headers.get("user-agent"),
        )
    except (NotFoundError, ValidationError, ConflictError) as e:
        raise _err(e)
    return result


# ===================== คอมเมนต์ (PIRI Talk) =====================
@router.post("/{board_id}/comments", response_model=BoardCommentOut)
async def add_comment(
    board_id: int,
    req: CommentCreateRequest,
    request: Request,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """💬 คอมเมนต์/รีพลายใน board (talk เท่านั้น — reply ผ่าน parent_id)"""
    uid = _ensure_user(user_ctx)
    try:
        comment_id = await board_service.add_comment(
            pool, uid, board_id, req.body, parent_id=req.parent_id,
            ip=_client_ip(request), user_agent=request.headers.get("user-agent"),
        )
        comment = await board_service.get_comment(pool, board_id, comment_id)
    except (NotFoundError, ForbiddenError, ValidationError) as e:
        raise _err(e)
    return BoardCommentOut(**comment)
