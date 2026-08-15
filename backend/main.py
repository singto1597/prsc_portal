from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncpg
import logging

from core.config import settings
from core.init_db import init_db

from routers import auth_router
from routers import issue_router
from routers import dashboard_router
from routers import student_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("API_MAIN")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """ก่อน yield = ตอนเปิด, หลัง yield = ตอนปิด"""
    logger.info("🚀 Starting PRSC Portal API...")

    try:
        app.state.db_pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=1,
            max_size=10
        )
        logger.info("✅ Database Connection Pool Created Successfully!")

        # 🚀 เรียกใช้ Schema Setup จาก core.init_db
        await init_db(app.state.db_pool)

    except Exception as e:
        logger.error(f"❌ Failed to connect to Database: {e}")
        raise e

    yield

    logger.info("🛑 Shutting down... Closing Database Pool.")
    await app.state.db_pool.close()
    logger.info("✅ Database Pool Closed.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="PRSC Portal API — ระบบรับความคิดเห็นและปัญหาสภานักเรียน",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://0.0.0.0:5173",
        "https://prsc-test.singto1597.xyz",
        "https://prsc-test.pirivoice.com",
        "https://www.pirivoice.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api")
app.include_router(issue_router.router, prefix="/api")
app.include_router(dashboard_router.router, prefix="/api")
app.include_router(student_router.router, prefix="/api")


@app.get("/health", tags=["Health"])
async def health_check():
    try:
        # ถ้า Pool ทำงานได้ SELECT 1 จะคืนค่า 1
        async with app.state.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "disconnected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
