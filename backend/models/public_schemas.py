"""Public (ไม่ต้องล็อกอิน) response schemas — ใช้กับ Landing Page / หน้าสาธารณะ

เปิดเผยเฉพาะข้อมูลภาพรวม + เรื่องที่ปิดแล้วแบบ mask ตัวตน เพื่อความปลอดภัยของข้อมูล
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class SystemStatsOut(BaseModel):
    """สถิติรวมของระบบ (Public)

    นำเสนอแบบเน้นความ Active ของระบบ (ไม่เน้นจุดจบคดี) — จึงแยก
    resolved_issues / routed_issues แทนการโชว์อัตราสำเร็จเป็นตัวเลขหลัก
    """
    total_issues: int          # เรื่องที่เข้าสู่ระบบแล้ว (ทั้งหมด)
    resolved_issues: int       # เรื่องที่ปิดสำเร็จแล้ว
    routed_issues: int         # เรื่องที่กำลังดำเนินการ / ส่งต่อฝ่ายที่เกี่ยวข้องแล้ว (in_progress + escalated)
    resolved_rate_percent: float  # เก็บไว้เพื่อความเข้ากันได้ (เดิม) — หน้า Landing ใหม่ไม่ใช้เป็นตัวเลขหลัก
    avg_resolve_hours: float
    active_talk_threads: int
    active_votes: int


class StatTrendPoint(BaseModel):
    """จำนวนเรื่องใหม่ที่เข้าสู่ระบบ 1 จุด (1 วัน) — สำหรับ sparkline"""
    date: date
    count: int


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
