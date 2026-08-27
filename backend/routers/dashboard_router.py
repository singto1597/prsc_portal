from fastapi import APIRouter, Depends, HTTPException
import asyncpg

from core.dependencies import get_db_pool, get_current_user
from core.exceptions import ForbiddenError
from models.dashboard_schemas import DashboardSummary, DashboardTraffic
from services import dashboard_service
from services import audit_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """สถิติหลักของระบบ (ต้องมีสิทธิ์ VIEW_DASHBOARD)"""
    uid = user_ctx.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")

    try:
        data = await dashboard_service.get_dashboard(pool, uid)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))
    # 🛡️ Audit: ดูแดชบอร์ด (best-effort)
    await audit_service.log_read(pool, uid, "READ_DASHBOARD", "dashboard", endpoint="GET /api/dashboard/summary")
    return DashboardSummary(**data)


@router.get("/traffic", response_model=DashboardTraffic)
async def get_dashboard_traffic(
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """สถิติการเข้าใช้งาน (30 วัน) — เฉพาะบทบาทระดับโรงเรียน (admin/ครูสภา/ประธานสภา/สภานักเรียน)"""
    uid = user_ctx.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")

    try:
        data = await dashboard_service.get_dashboard_traffic(pool, uid)
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))
    # 🛡️ Audit: ดูสถิติการใช้งาน (best-effort)
    await audit_service.log_read(pool, uid, "READ_DASHBOARD_TRAFFIC", "dashboard", endpoint="GET /api/dashboard/traffic")
    return DashboardTraffic(**data)
