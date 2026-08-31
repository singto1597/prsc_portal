from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class NotificationOut(BaseModel):
    id: int
    group_type: str
    type: str
    title: str
    body: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    board_id: Optional[int] = None
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationListOut(BaseModel):
    items: List[NotificationOut]
    total: int
    page: int
    page_size: int
    pages: int


class UnreadCountsOut(BaseModel):
    counts: dict[str, int]  # {"issue_mine": 1, "issue_received": 0, "board": 3, "report": 0}
    total: int


class MarkReadRequest(BaseModel):
    # อย่างน้อยต้องระบุหนึ่งอย่าง หรือ read_all=True (กันเผลอเคลียร์ทุกอย่าง)
    ids: Optional[List[int]] = None
    group_type: Optional[str] = Field(None, pattern="^(issue_mine|issue_received|board|report)$")
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    board_id: Optional[int] = None
    read_all: bool = Field(False, description="อ่านทั้งหมด (เคลียร์ทุกกลุ่ม)")


class MarkReadOut(BaseModel):
    updated: int
