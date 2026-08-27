from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg
from datetime import date

from core.dependencies import get_db_pool, get_current_user
from core.exceptions import ForbiddenError
from models.audit_schemas import AuditLogListOut, AuditLogOut
from services import audit_service

router = APIRouter(prefix="/audit-logs", tags=["AuditLogs"])


@router.get("", response_model=AuditLogListOut)
async def list_audit_logs(
    action: str | None = Query(None, max_length=50, description="กรองตาม action เช่น login/CREATE_ISSUE"),
    entity_type: str | None = Query(None, max_length=50, description="กรองตามชนิด entity เช่น issue/user"),
    entity_id: str | None = Query(None, max_length=50, description="กรองตาม id ของ entity"),
    status: str | None = Query(None, max_length=20, description="success/error/partial"),
    q: str | None = Query(None, max_length=100, description="ค้นหาตามชื่อผู้ใช้/ข้อความ error"),
    date_from: date | None = Query(None, description="จากวันที่ (YYYY-MM-DD, Asia/Bangkok)"),
    date_to: date | None = Query(None, description="ถึงวันที่ (YYYY-MM-DD, Asia/Bangkok)"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """ประวัติการใช้งานทั้งหมด (เฉพาะ VIEW_AUDIT_LOG + scope super/all — admin/ครูสภา/ประธานสภา)"""
    uid = user_ctx.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")

    try:
        result = await audit_service.list_audit_logs(
            pool, uid,
            action=action, entity_type=entity_type, entity_id=entity_id,
            status=status, q=q, date_from=date_from, date_to=date_to,
            limit=limit, offset=offset,
        )
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return AuditLogListOut(
        items=[AuditLogOut(**i) for i in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"],
    )
