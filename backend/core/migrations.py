"""
🔄 Migration Runner สำหรับ PIRIvoice

ระบบนี้ไม่มี ORM — schema ถูกสร้างโดย init_db (CREATE TABLE IF NOT EXISTS)
ซึ่งไม่ช่วยอัปเกรด DB ที่มีข้อมูลอยู่แล้ว ดังนั้นจึงมี migration files:
- แต่ละไฟล์ใน backend/migrations/ ต้องมี VERSION, DESCRIPTION, async def upgrade(conn)
- runner เก็บประวัติที่รันไปแล้วในตาราง `schema_migrations` (กันรันซ้ำ)
- เรียกจาก init_db ตอนท้ายสุด → ทั้ง DB ใหม่และ DB เดิมได้ schema ที่ตรงกัน
"""
import os
import sys
import importlib.util
import logging

logger = logging.getLogger("API_MIGRATIONS")

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")


def _discover_migrations() -> list:
    """โหลดทุกไฟล์ .py ใน backend/migrations/ (ยกเว้น _*) แล้วเรียงตาม VERSION"""
    mods = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return mods
    for fname in sorted(os.listdir(MIGRATIONS_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        version = fname[:-3]
        path = os.path.join(MIGRATIONS_DIR, fname)
        spec = importlib.util.spec_from_file_location(version, path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            logger.error(f"❌ โหลด migration {fname} ไม่สำเร็จ: {e}")
            raise e
        if not hasattr(mod, "upgrade"):
            logger.warning(f"⚠️ migration {fname} ไม่มีฟังก์ชัน upgrade — ข้าม")
            continue
        mods.append(mod)
    return sorted(mods, key=lambda m: getattr(m, "VERSION", "0"))


async def run_migrations(pool) -> None:
    """
    รัน migration ที่ยังไม่เคยรัน (เรียงตาม VERSION) ภายใน transaction เดียว
    ปลอดภัยสำหรับการรันซ้ำ (idempotent ผ่านตาราง schema_migrations)
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    description TEXT,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            applied = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")}
            for mig in _discover_migrations():
                version = getattr(mig, "VERSION", None)
                if not version or version in applied:
                    continue
                description = getattr(mig, "DESCRIPTION", "")
                await mig.upgrade(conn)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, description) VALUES ($1, $2)",
                    version, description
                )
                logger.info(f"✅ Applied migration: {version} — {description}")
