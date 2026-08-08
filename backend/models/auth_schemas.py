from typing import Optional, List
from pydantic import BaseModel, Field


# ===================== Request =====================
class LoginRequest(BaseModel):
    username: str = Field(..., description="รหัสนักเรียน หรือ username")
    password: str = Field(..., min_length=4, description="รหัสผ่าน")


class RegisterRequest(BaseModel):
    username: str = Field(..., description="รหัสนักเรียน")
    password: str = Field(..., min_length=4)
    full_name: str = Field(..., description="ชื่อ-นามสกุล")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="รหัสผ่านเดิม")
    new_password: str = Field(..., min_length=4, description="รหัสผ่านใหม่")


# ===================== Response =====================
class UserRoleInfo(BaseModel):
    role: Optional[str] = None          # ตำแหน่ง เช่น class_president, vice_academic
    room_id: Optional[int] = None
    room_name: Optional[str] = None
    student_no: Optional[int] = None
    level: Optional[str] = None         # ระดับชั้น เช่น ม.4


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    is_admin: bool = False
    permissions: List[str] = []
    # ข้อมูลตำแหน่ง (อาจมีได้หลายห้อง แต่ใช้ห้องหลักก่อน)
    roles: List[UserRoleInfo] = []


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
