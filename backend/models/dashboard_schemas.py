from typing import List, Optional
from pydantic import BaseModel


class CountStat(BaseModel):
    label: str
    count: int


class CategoryStat(BaseModel):
    category: str
    label: str
    count: int


class StatusStat(BaseModel):
    status: str
    label: str
    count: int


class TrendPoint(BaseModel):
    date: str
    count: int


class DashboardSummary(BaseModel):
    total_issues: int
    pending: int
    in_progress: int
    resolved: int
    escalated: int
    total_students: int
    total_rooms: int
    # หมวดหมู่
    top_categories: List[CategoryStat] = []
    # สถานะ
    by_status: List[StatusStat] = []
    # แนวโน้ม (รายวัน 7 วัน)
    trend: List[TrendPoint] = []
    # การเข้าใช้งาน (จาก audit_logs)
    usage_count: int = 0
    recent_logins: List[dict] = []
