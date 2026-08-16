import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "PRSC Portal API (Issue & Feedback)"
    PROJECT_VERSION: str = "1.0.0"

    DATABASE_URL: str
    API_KEY: str
    SECRET_KEY: str
    SUPER_ADMIN_ID: int = 0

    # JWT Settings
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # Redis (สำหรับ event/notification — อาจยังไม่ใช้ใน v1 แต่ config ให้พร้อม)
    REDIS_URL: str = ""

    # Queue Import นักเรียนจาก Excel (ARQ Worker)
    # - IMPORT_STORAGE_DIR: โฟลเดอร์เก็บไฟล์ .xlsx ที่อัปโหลด (shared volume ระหว่าง backend + worker)
    #   ใน Docker = /data/imports (mount จาก docker-compose.app.yml) ; dev ในเครื่อง = ตั้งเองใน .env
    IMPORT_STORAGE_DIR: str = "/data/imports"
    # จำกัดขนาดไฟล์ Excel ที่รับอัปโหลด (MB) — ป้องกันไฟล์ยักษ์ลาก worker
    IMPORT_FILE_SIZE_LIMIT_MB: int = 10
    # จำนวนแถวต่อ 1 batch เมื่อ worker ทยอย insert (คุมหน่วยความจำ + ความถี่ของการ update progress)
    IMPORT_BATCH_SIZE: int = 50
    # จำนวนแถวสูงสุดต่อไฟล์ (กันไฟล์ยักษ์ลาก worker นานเป็นชั่วโมง — DoS)
    IMPORT_MAX_ROWS: int = 5000
    # อายุงานค้าง (นาที) ที่ worker กู้คืนตอนเริ่มต้น — PROCESSING/QUEUED ค้างเกินนี้ → reset กลับ QUEUED
    IMPORT_RECOVERY_STALE_MINUTES: int = 35

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
