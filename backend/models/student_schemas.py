from typing import Optional, List
from pydantic import BaseModel, Field


# ===================== Room =====================
class RoomOut(BaseModel):
    id: int
    room_code: str
    room_name: str
    level: Optional[str] = None
    room_number: Optional[int] = None


# ===================== Student =====================
class StudentOut(BaseModel):
    id: int
    room_id: Optional[int] = None
    room_code: Optional[str] = None
    room_name: Optional[str] = None
    student_id: str
    student_no: Optional[int] = None
    prefix: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    class_role: str
    staff_level: Optional[str] = None   # ระดับชั้นที่ครูทั่วไปรับผิดชอบ เช่น 'ม.4'
    is_admin: bool = False
    permissions: List[str] = []
    status: str = "active"


class StudentUpdateRequest(BaseModel):
    class_role: Optional[str] = None
    status: Optional[str] = None
    is_admin: Optional[bool] = None
    staff_level: Optional[str] = None   # อัปเดตระดับชั้นที่ครูดูแลได้


# ===================== My Profile =====================
class MyProfileOut(BaseModel):
    id: int
    student_id: str
    student_no: Optional[int] = None
    prefix: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    class_role: str
    staff_level: Optional[str] = None   # ระดับชั้นที่ครูทั่วไปรับผิดชอบ
    status: str
    room_id: Optional[int] = None
    room_code: Optional[str] = None
    room_name: Optional[str] = None
    level: Optional[str] = None
    # จาก users
    username: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    prefix: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
