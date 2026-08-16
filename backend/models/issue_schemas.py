from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

from core.categories import all_main_category_codes, is_valid_category


# ===================== สร้างปัญหา =====================
class IssueCreateRequest(BaseModel):
    # หมวดหลัก: suggestion (เสนอความคิดเห็น) / wellbeing (สุขภาวะทางกายและใจ) / report (แจ้งเหตุ)
    main_category: str = Field(..., description="หมวดหลัก: suggestion / wellbeing / report")
    # หมวดย่อยในหมวดหลัก (ตาม config/categories.json)
    category: str = Field(..., description="หมวดย่อยของหมวดหลัก")
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=3)
    is_anonymous: bool = False
    # ระบุห้องที่แจ้ง (default = ห้องตัวเอง ถ้าไม่ระบุ)
    room_id: Optional[int] = None
    # ระดับเริ่มต้นของเรื่อง (room/level/council) — default room
    # เฉพาะผู้มีระดับสูงขึ้นจึงเลือกได้
    start_level: str = "room"

    @field_validator("main_category")
    @classmethod
    def _validate_main_category(cls, v: str) -> str:
        if v not in all_main_category_codes():
            raise ValueError(f"หมวดหลักไม่ถูกต้อง: {v} (ต้องเป็น {', '.join(all_main_category_codes())})")
        return v

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: str, info) -> str:
        main_cat = info.data.get("main_category")
        if main_cat and not is_valid_category(main_cat, v):
            raise ValueError(f"หมวดย่อย '{v}' ไม่ได้อยู่ในหมวดหลัก '{main_cat}'")
        return v


class StepCreateRequest(BaseModel):
    step_title: str = Field(..., min_length=1, max_length=200)
    step_detail: Optional[str] = None


class CountdownSetRequest(BaseModel):
    estimated_days: int = Field(..., ge=1, le=365, description="จำนวนวันที่ใช้แก้ปัญหา")


class EscalateRequest(BaseModel):
    reason: Optional[str] = None


# ===================== Response =====================
class IssueStepOut(BaseModel):
    id: int
    step_title: str
    step_detail: Optional[str] = None
    step_order: int
    is_completed: bool
    completed_at: Optional[datetime] = None


class IssueCountdownOut(BaseModel):
    id: int
    estimated_days: int
    started_at: datetime
    deadline: datetime
    is_overdue: bool


class EscalationOut(BaseModel):
    id: int
    from_level: str
    to_level: str
    reason: Optional[str] = None
    created_at: datetime


class StatusHistoryOut(BaseModel):
    id: int
    status: str
    note: Optional[str] = None
    created_at: datetime


class IssueOut(BaseModel):
    id: int
    room_id: Optional[int] = None
    room_name: Optional[str] = None
    main_category: str
    category: str
    title: str
    description: str
    image_url: Optional[str] = None
    reporter_id: Optional[int] = None
    reporter_name: Optional[str] = None
    reporter_room: Optional[str] = None
    current_level: str
    current_assignee_id: Optional[int] = None
    current_assignee_role: Optional[str] = None
    current_assignee_name: Optional[str] = None
    status: str
    priority: str
    is_anonymous: bool
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # รายละเอียดเสริม (เฉพาะ detail)
    steps: List[IssueStepOut] = []
    countdown: Optional[IssueCountdownOut] = None
    escalations: List[EscalationOut] = []
    status_history: List[StatusHistoryOut] = []
