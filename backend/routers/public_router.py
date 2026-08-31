"""Public Router — ข้อมูลสาธารณะ (ไม่ต้องล็อกอิน) สำหรับ Landing Page

ติดตั้งที่ prefix /api/v1 ใน main.py → เส้นทางจริง: /api/v1/public/...
"""
from fastapi import APIRouter, Depends, Query
import asyncpg

from core.dependencies import get_db_pool
from models.public_schemas import (
    SystemStatsOut,
    ResolvedCaseOut,
    AnnouncementOut,
)
from services import public_service

router = APIRouter(prefix="/public", tags=["Public"])


@router.get("/stats", response_model=SystemStatsOut)
async def get_system_stats(pool: asyncpg.Pool = Depends(get_db_pool)):
    return await public_service.get_system_stats(pool)


@router.get("/resolved-cases", response_model=list[ResolvedCaseOut])
async def get_resolved_cases(
    limit: int = Query(5, ge=1, le=50),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    return await public_service.get_resolved_cases(pool, limit)


@router.get("/announcements", response_model=list[AnnouncementOut])
async def get_announcements(pool: asyncpg.Pool = Depends(get_db_pool)):
    return await public_service.get_announcements(pool)
