from fastapi import APIRouter, Depends, HTTPException
import asyncpg

from core.dependencies import get_db_pool, get_current_user
from core.exceptions import ForbiddenError, NotFoundError, ConflictError, ValidationError
from models.auth_schemas import LoginRequest, LoginResponse, UserOut, ChangePasswordRequest
from services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, pool: asyncpg.Pool = Depends(get_db_pool)):
    """เข้าสู่ระบบด้วยรหัสนักเรียน/รหัสผ่าน → ได้ JWT"""
    try:
        user_id = await auth_service.authenticate_user(pool, req.username, req.password)
    except (NotFoundError, ForbiddenError) as e:
        raise HTTPException(status_code=401, detail=str(e))

    user = await auth_service.get_user_by_id(pool, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้")

    roles = await auth_service.get_user_roles(pool, user_id)
    token = auth_service.create_access_token(user_id)

    return LoginResponse(
        access_token=token,
        user=UserOut(**auth_service.make_user_out(user, roles)),
    )


@router.get("/me", response_model=UserOut)
async def get_me(
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """ดึงข้อมูลผู้ใช้ปัจจุบัน (ใช้ในการ refresh session)"""
    if not user_ctx.get("user_id"):
        raise HTTPException(status_code=401, detail="ไม่พบ user_id")

    user = await auth_service.get_user_by_id(pool, user_ctx["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้")

    roles = await auth_service.get_user_roles(pool, user_ctx["user_id"])
    return UserOut(**auth_service.make_user_out(user, roles))


@router.post("/change-password", response_model=dict)
async def change_password(
    req: ChangePasswordRequest,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """เปลี่ยนรหัสผ่าน (ตรวจรหัสเดิมก่อน)"""
    if not user_ctx.get("user_id"):
        raise HTTPException(status_code=401, detail="ไม่พบ user_id")

    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="รหัสผ่านใหม่ต้องไม่เหมือนรหัสเก่า")

    try:
        await auth_service.change_password(pool, user_ctx["user_id"], req.old_password, req.new_password)
    except (NotFoundError, ForbiddenError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok", "message": "เปลี่ยนรหัสผ่านสำเร็จ"}
