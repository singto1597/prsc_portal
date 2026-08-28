"""
PIRI Boards — Pydantic v2 Schemas (PIRI Vote + PIRI Talk)

แบ่งเป็น 2 กลุ่ม:
- Request: VoteSubmitRequest (โหวต), CommentCreateRequest (คอมเมนต์)
- Response: BoardSummaryOut (รายการ), BoardDetailOut (รายละเอียด), BoardCommentOut (threaded)

หมายเหตุ: `response_model` ทำหน้าที่กรอง field หวงห้าม (เช่น อย่าให้ secret รั่ว) ตามกฎ backend.md
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


# ===================== Request =====================
class VoteSubmitRequest(BaseModel):
    """ส่งเสียงโหวต — ผู้ใช้โหวตได้ 1 เสียงต่อ board (โหวตซ้ำ → 409)"""
    choice_id: int = Field(..., description="ตัวเลือกที่โหวต (id ใน piri_vote_choices)")


class CommentCreateRequest(BaseModel):
    """คอมเมนต์/รีพลายใน board (PIRI Talk)"""
    body: str = Field(..., min_length=1, max_length=1000)
    parent_id: Optional[int] = Field(None, description="reply ต่อคอมเมนต์ (id ของคอมเมนต์ต้นทาง)")


# ===================== Response =====================
class VoteChoiceOut(BaseModel):
    """ตัวเลือกโหวต 1 อัน (มี vote_count เพื่อคำนวณ % บน frontend)"""
    id: int
    choice_text: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int
    vote_count: int


class VoteResultOut(BaseModel):
    """ผลการโหวต — typed response (ไม่ใช่ dict เปล่า) ตามกฎ response_model กรอง field หวงห้าม"""
    status: str
    vote_id: int
    board_id: int
    choice_id: int
    choice_text: str


class BoardCommentOut(BaseModel):
    """คอมเมนต์ใน board — แบบ threaded (replies ซ้อนกัน; ความลึกถูกจำกัดฝั่ง service
    กัน recursive Pydantic overflow — reply ลึกเกินถูกพับใต้บรรพบุรุษ, ไม่หาย)"""
    id: int
    parent_comment_id: Optional[int] = None
    user_id: Optional[int] = None
    commenter_name: Optional[str] = None
    body: str
    is_edited: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    replies: List["BoardCommentOut"] = []


class BoardSummaryOut(BaseModel):
    """การ์ด board ใน feed — ไม่มี pyramid visibility (ข้อมูลสาธารณะ)"""
    id: int
    board_type: str
    title: str
    description: str
    cover_image_url: Optional[str] = None
    source_issue_id: Optional[int] = None
    author_id: Optional[int] = None
    author_name: Optional[str] = None          # None ถ้า board anonymous (is_anonymous=True)
    is_anonymous: bool
    comment_count: int
    view_count: int
    status: str
    tags: List[str] = []
    total_votes: int = 0                       # เฉพาะ vote board (รวมทุก choice) — ให้การ์ดโชว์ยอด
    created_at: datetime


class BoardDetailOut(BoardSummaryOut):
    """รายละเอียด board — vote: choices + my_vote; talk: comments (threaded)"""
    allow_comments: bool
    my_vote_choice_id: Optional[int] = None    # board ที่ user โหวตแล้ว (ชี้ choice_id) — ใช้ highlight ปุ่ม
    choices: List[VoteChoiceOut] = []
    comments: List[BoardCommentOut] = []


class BoardListOut(BaseModel):
    """feed แบบแบ่งหน้า (pattern เดียวกับ /issues)"""
    items: List[BoardSummaryOut]
    total: int
    page: int
    page_size: int
    pages: int


BoardCommentOut.model_rebuild()
