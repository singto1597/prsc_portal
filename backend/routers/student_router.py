from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
import asyncpg

from core.dependencies import get_db_pool, get_current_user
from core.rbac import require_permission_anywhere
from core.exceptions import NotFoundError, ForbiddenError, ValidationError
from models.student_schemas import (
    StudentOut, StudentUpdateRequest, ImportResult, RoomOut,
    MyProfileOut, UpdateProfileRequest,
)
from services import student_service

router = APIRouter(tags=["Students"])


# ===================== My Profile =====================
@router.get("/students/me/profile", response_model=MyProfileOut)
async def get_my_profile(
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """ดูโปรไฟล์ตัวเอง"""
    uid = user_ctx.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")

    try:
        profile = await student_service.get_my_profile(pool, uid)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return MyProfileOut(**profile)


@router.patch("/students/me/profile", response_model=MyProfileOut)
async def update_my_profile(
    req: UpdateProfileRequest,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """แก้ไขโปรไฟล์ตัวเอง (เฉพาะฟิลด์ที่ส่ง)"""
    uid = user_ctx.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")

    try:
        await student_service.update_my_profile(
            pool, uid,
            prefix=req.prefix, first_name=req.first_name, last_name=req.last_name,
            nickname=req.nickname, phone_number=req.phone_number, email=req.email,
        )
        profile = await student_service.get_my_profile(pool, uid)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return MyProfileOut(**profile)


@router.get("/rooms", response_model=list[RoomOut])
async def list_rooms(
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """รายการห้องเรียนทั้งหมด (สำหรับ dropdown)"""
    rooms = await student_service.list_rooms(pool)
    return [RoomOut(**r) for r in rooms]


@router.get("/students", response_model=list[StudentOut])
async def list_students(
    room_id: int | None = Query(None),
    search: str | None = Query(None),
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """รายชื่อนักเรียน (filter ตามห้อง / ค้นหา) — ต้องมีสิทธิ์ MANAGE_STUDENTS"""
    if not user_ctx.get("user_id"):
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")

    # ตรวจสิทธิ์ (Super Admin / is_admin ผ่าน)
    async with pool.acquire() as conn:
        try:
            await require_permission_anywhere(conn, user_ctx["user_id"], "MANAGE_STUDENTS")
        except ForbiddenError as e:
            raise HTTPException(status_code=403, detail=str(e))

    students = await student_service.list_students(pool, room_id=room_id, search=search)
    return [StudentOut(**s) for s in students]


@router.post("/students/import", response_model=ImportResult)
async def import_students(
    file: UploadFile = File(...),
    default_password: str = Query("1234"),
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """นำเข้านักเรียนจากไฟล์ Excel (.xlsx)
    คอลัมน์: รหัสนักเรียน | ห้องเรียน | เลขที่ | คำนำหน้า | ชื่อ | นามสกุล | ชื่อเล่น | ตำแหน่งในห้องเรียน
    """
    if not user_ctx.get("user_id"):
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")

    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ .xlsx")

    # ตรวจสิทธิ์
    async with pool.acquire() as conn:
        try:
            await require_permission_anywhere(conn, user_ctx["user_id"], "MANAGE_STUDENTS")
        except ForbiddenError as e:
            raise HTTPException(status_code=403, detail=str(e))

    content = await file.read()
    try:
        result = await student_service.import_students_from_excel(pool, content, default_password=default_password)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ImportResult(**result)


@router.patch("/students/{student_id}", response_model=dict)
async def update_student(
    student_id: int,
    req: StudentUpdateRequest,
    user_ctx: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_db_pool),
):
    """แก้ไขตำแหน่ง/สถานะนักเรียน (ต้องมี MANAGE_STUDENTS)"""
    if not user_ctx.get("user_id"):
        raise HTTPException(status_code=401, detail="ต้องเข้าสู่ระบบ")

    async with pool.acquire() as conn:
        try:
            await require_permission_anywhere(conn, user_ctx["user_id"], "MANAGE_STUDENTS")
        except ForbiddenError as e:
            raise HTTPException(status_code=403, detail=str(e))

    try:
        await student_service.update_student(
            pool, student_id,
            class_role=req.class_role,
            status=req.status,
            is_admin=req.is_admin,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"status": "ok"}
