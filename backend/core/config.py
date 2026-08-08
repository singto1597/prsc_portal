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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
