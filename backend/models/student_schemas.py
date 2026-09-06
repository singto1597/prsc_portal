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
    responsibilities: List[str] = []    # หน้าที่รับผิดชอบ (สภานักเรียน/ผู้ช่วยหัวหน้าระดับ) — ตรงกับ issues.category
    status: str = "active"


class StudentUpdateRequest(BaseModel):
    class_role: Optional[str] = None
    status: Optional[str] = None
    is_admin: Optional[bool] = None
    staff_level: Optional[str] = None   # อัปเดตระดับชั้นที่ครูดูแลได้
    responsibilities: Optional[List[str]] = None   # แก้หน้าที่รับผิดชอบได้ (เฉพาะ role ที่มีหน้าที่)


class StudentCreateRequest(BaseModel):
    """เพิ่มผู้ใช้งานแบบ Manual (สำหรับกรณี import Excel ไม่ครบ)"""
    username: str = Field(..., description="รหัสนักเรียน/username")
    password: Optional[str] = Field(None, min_length=4, description="รหัสผ่าน (ถ้าไม่ระบุ = เปลี่ยนครั้งแรก)")
    prefix: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None
    room_code: Optional[str] = Field(None, description="รหัสห้อง เช่น ม.4/1 — สร้างห้องให้ถ้าไม่มี")
    class_role: str = Field(..., description="ตำแหน่ง เช่น council_member / level_vice_president / class_president")
    responsibilities: Optional[List[str]] = None   # หน้าที่รับผิดชอบ (เฉพาะ role ที่มีหน้าที่)


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
