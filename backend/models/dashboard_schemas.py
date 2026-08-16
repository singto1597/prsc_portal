from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


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


class RecentIssueOut(BaseModel):
    """เรื่องล่าสุดในหมวด (สำหรับคลิกเข้าไปติดตามต่อ)"""
    id: int
    title: str
    main_category: str
    category: str
    category_label: str
    status: str
    current_level: str
    room_name: Optional[str] = None
    created_at: datetime


class MainCategoryDashboard(BaseModel):
    """สถิติรายหมวดหลัก (suggestion / wellbeing / report)"""
    code: str
    label: str
    total: int
    by_status: List[StatusStat] = []
    top_subcategories: List[CategoryStat] = []
    recent_issues: List[RecentIssueOut] = []


class DashboardSummary(BaseModel):
    # ขอบเขตข้อมูล: 'all' = ทั้งโรงเรียน, 'level' = เฉพาะระดับชั้น (ครูทั่วไป)
    scope: str
    scope_label: Optional[str] = None     # เช่น 'ม.4' — เฉพาะ scope='level'

    total_issues: int
    pending: int
    in_progress: int
    resolved: int
    escalated: int
    cancelled: int
    overdue: int                          # งานกำลังดำเนินการที่เกินกำหนดเวลา
    total_students: int
    total_rooms: int

    # สถานะรวมทั้งระบบ
    by_status: List[StatusStat] = []
    # 📊 หัวใจ: สถิติแยกตาม 3 หมวดหลัก
    main_categories: List[MainCategoryDashboard] = []
    # แนวโน้ม (รายวัน 7 วัน)
    trend: List[TrendPoint] = []
    # การเข้าใช้งาน (จาก audit_logs — best effort)
    usage_count: int = 0
    recent_logins: List[dict] = []
