from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from core.dependencies import get_db_pool, get_current_user
from core.exceptions import NotFoundError, ForbiddenError, ValidationError, ConflictError
from models.issue_schemas import (
    IssueCreateRequest, IssueOut, IssueStepOut, IssueCountdownOut,
    StepCreateRequest, CountdownSetRequest, EscalateRequest,
)
from services import issue_service

router = APIRouter(prefix="/issues", tags=["Issues"])


def _ensure_user(user_ctx: dict) -> int:
    """ดึง user_id หรือ raise 401"""
    uid = user_ctx.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")
    return uid


def _err(e: Exception):
    """แปลง domain exception → HTTPException"""
    if isinstance(e, NotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ForbiddenError):
        return HTTPException(status_code=403, detail=str(e))
    if isinstance(e, ValidationError):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, ConflictError):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาด: {e}")


@router.post("", response_model=IssueOut)
async def create_issue(
    req: IssueCreateRequest,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """สร้างปัญหาใหม่ (เริ่มที่ระดับห้อง หรือระดับที่เลือกได้สำหรับผู้มีสิทธิ์)"""
    uid = _ensure_user(user_ctx)
    try:
        issue_id = await issue_service.create_issue(
            pool, uid, req.topic_type, req.category, req.title,
            req.description, req.is_anonymous, req.room_id,
            req.start_level,
        )
        issue = await issue_service.get_issue(pool, uid, issue_id)
    except (NotFoundError, ValidationError, ForbiddenError) as e:
        raise _err(e)
    return IssueOut(**issue)


@router.get("", response_model=list[IssueOut])
async def list_issues(
    mine: bool = Query(False, description="เฉพาะเรื่องที่ฉันแจ้ง"),
    received: bool = Query(False, description="เรื่องที่ฉันรับ/อยู่ในระดับฉัน (มองเห็นได้ทั้งหมด)"),
    status: str | None = Query(None),
    category: str | None = Query(None),
    level: str | None = Query(None, description="กรองตามระดับ: room/level/council"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """รายการปัญหา (visibility ตามพีระมิด + ตัวกรอง)"""
    uid = _ensure_user(user_ctx)
    issues = await issue_service.list_issues(
        pool, uid, only_mine=mine, received=received,
        status_filter=status, category=category, level_filter=level,
        limit=limit, offset=offset,
    )
    return [IssueOut(**i) for i in issues]


@router.get("/{issue_id}", response_model=IssueOut)
async def get_issue(
    issue_id: int,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """ดูรายละเอียดปัญหา"""
    uid = _ensure_user(user_ctx)
    try:
        issue = await issue_service.get_issue(pool, uid, issue_id)
    except (NotFoundError, ForbiddenError) as e:
        raise _err(e)
    return IssueOut(**issue)


# ==================== รับเรื่อง + Countdown ====================
@router.post("/{issue_id}/accept", response_model=dict)
async def accept_issue(
    issue_id: int,
    req: CountdownSetRequest,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """รับเรื่อง + ตั้งเวลานับถอยหลัง (กี่วัน)"""
    uid = _ensure_user(user_ctx)
    try:
        await issue_service.accept_issue(pool, uid, issue_id, req.estimated_days)
    except (NotFoundError, ForbiddenError, ValidationError) as e:
        raise _err(e)
    return {"status": "accepted"}


@router.patch("/{issue_id}/countdown", response_model=dict)
async def update_countdown(
    issue_id: int,
    req: CountdownSetRequest,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """แก้ไข countdown (ยืดเวลา)"""
    uid = _ensure_user(user_ctx)
    try:
        await issue_service.update_countdown(pool, uid, issue_id, req.estimated_days)
    except (NotFoundError, ForbiddenError, ValidationError) as e:
        raise _err(e)
    return {"status": "ok"}


# ==================== Steps ====================
@router.post("/{issue_id}/steps", response_model=IssueStepOut)
async def add_step(
    issue_id: int,
    req: StepCreateRequest,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """เพิ่มขั้นตอนการดำเนินงาน"""
    uid = _ensure_user(user_ctx)
    try:
        step_id = await issue_service.add_step(pool, uid, issue_id, req.step_title, req.step_detail)
    except (NotFoundError, ForbiddenError, ValidationError) as e:
        raise _err(e)

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM issue_steps WHERE id = $1", step_id)
    return IssueStepOut(**issue_service._step_to_dict(row))


@router.patch("/{issue_id}/steps/{step_id}/complete", response_model=dict)
async def complete_step(
    issue_id: int,
    step_id: int,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """ทำขั้นตอนสำเร็จ"""
    uid = _ensure_user(user_ctx)
    try:
        await issue_service.complete_step(pool, uid, issue_id, step_id)
    except (NotFoundError, ForbiddenError) as e:
        raise _err(e)
    return {"status": "ok"}


# ==================== Escalate / Resolve ====================
@router.post("/{issue_id}/escalate", response_model=dict)
async def escalate_issue(
    issue_id: int,
    req: EscalateRequest,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """ส่งต่อไประดับบน (เกินความสามารถ/ไม่ทัน)"""
    uid = _ensure_user(user_ctx)
    try:
        await issue_service.escalate_issue(pool, uid, issue_id, req.reason)
    except (NotFoundError, ForbiddenError, ValidationError) as e:
        raise _err(e)
    return {"status": "escalated"}


@router.post("/{issue_id}/resolve", response_model=dict)
async def resolve_issue(
    issue_id: int,
    req: EscalateRequest,  # reuse (มี field note? ใช้ reason เป็น note)
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """ปิดเรื่อง (แก้ไขเสร็จสิ้น)"""
    uid = _ensure_user(user_ctx)
    try:
        await issue_service.resolve_issue(pool, uid, issue_id, req.reason)
    except (NotFoundError, ForbiddenError, ValidationError) as e:
        raise _err(e)
    return {"status": "resolved"}


@router.post("/{issue_id}/cancel", response_model=dict)
async def cancel_issue(
    issue_id: int,
    req: EscalateRequest,  # reuse (field reason = เหตุผลยกเลิก)
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """ยกเลิกเรื่อง (ผู้แจ้ง — กันส่งผิด)"""
    uid = _ensure_user(user_ctx)
    try:
        await issue_service.cancel_issue(pool, uid, issue_id, req.reason)
    except (NotFoundError, ForbiddenError, ValidationError) as e:
        raise _err(e)
    return {"status": "cancelled"}
