from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from core.dependencies import get_db_pool, get_current_user
from core.rbac import require_permission_anywhere, get_access_scope
from core.exceptions import NotFoundError, ForbiddenError
from models.student_schemas import (
    StudentOut, StudentUpdateRequest, RoomOut,
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

    # ตรวจสิทธิ์ (Super Admin / is_admin ผ่าน) + หา scope (ครูทั่วไปเห็นได้เฉพาะระดับชั้นตัวเอง)
    async with pool.acquire() as conn:
        try:
            await require_permission_anywhere(conn, user_ctx["user_id"], "MANAGE_STUDENTS")
        except ForbiddenError as e:
            raise HTTPException(status_code=403, detail=str(e))
        scope = await get_access_scope(conn, user_ctx["user_id"])

    level = scope.get("level") if scope["scope"] == "level" else None
    students = await student_service.list_students(pool, room_id=room_id, search=search, level=level)
    return [StudentOut(**s) for s in students]


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
        scope = await get_access_scope(conn, user_ctx["user_id"])
        # 🛡️ ครูทั่วไปแก้ได้เฉพาะนักเรียนในระดับชั้นตัวเอง
        if scope["scope"] == "level":
            target_level = await conn.fetchval(
                """
                SELECT r.level FROM students s
                JOIN rooms r ON r.id = s.room_id
                WHERE s.id = $1 AND s.deleted_at IS NULL
                """,
                student_id
            )
            if not target_level:
                raise HTTPException(status_code=404, detail="ไม่พบนักเรียน")
            if target_level != scope["level"]:
                raise HTTPException(status_code=403, detail=f"คุณดูแลได้เฉพาะระดับ {scope['level']}")

    try:
        await student_service.update_student(
            pool, student_id,
            class_role=req.class_role,
            status=req.status,
            is_admin=req.is_admin,
            staff_level=req.staff_level,
            actor_user_id=user_ctx["user_id"],
            client_source="web",
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"status": "ok"}
