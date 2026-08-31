"""Public (ไม่ต้องล็อกอิน) response schemas — ใช้กับ Landing Page / หน้าสาธารณะ

เปิดเผยเฉพาะข้อมูลภาพรวม + เรื่องที่ปิดแล้วแบบ mask ตัวตน เพื่อความปลอดภัยของข้อมูล
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SystemStatsOut(BaseModel):
    """สถิติรวมของระบบ (Public)"""
    total_issues: int
    resolved_rate_percent: float
    avg_resolve_hours: float
    active_talk_threads: int
    active_votes: int


class ResolvedCaseOut(BaseModel):
    """เรื่องที่ปิดงานแล้ว (Public) — mask ตัวตนผู้แจ้งเสมอ"""
    id: str
    title: str
    category: str
    reporter_mask: str
    resolved_at: datetime
    solution_summary: str
    department_in_charge: str
    impact_score: int
    duration_hours: Optional[float] = None


class AnnouncementOut(BaseModel):
    """ประกาศสาธารณะ"""
    id: int
    message: str
    priority: str  # normal / high / urgent
    link: Optional[str] = None
