from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


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


class SubcategoryDashboard(BaseModel):
    """สถิติรายหมวดย่อย — นับเรื่อง + สถานะภายในหมวดย่อย (เรียง count จากมากไปน้อย)"""
    category: str
    label: str
    description: str = ""       # คำอธิบายหมวดย่อย (จาก config/categories.json)
    count: int
    by_status: List[StatusStat] = []


class MainCategoryDashboard(BaseModel):
    """สถิติรายหมวดหลัก (suggestion / wellbeing / report)"""
    code: str
    label: str
    description: str = ""       # คำอธิบายหมวดหลัก (จาก config/categories.json)
    total: int
    overdue: int = 0            # งานในหมวดนี้ที่เกินกำหนดเวลา
    by_status: List[StatusStat] = []
    subcategories: List[SubcategoryDashboard] = []
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
