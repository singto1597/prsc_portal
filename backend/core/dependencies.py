from fastapi import Request, Security, HTTPException, status, Header, Depends
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import asyncpg
from typing import Optional

from core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

async def get_db_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool

def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    return api_key

# 🚀 แปลงทุก Request ให้เป็น user_id ผ่าน JWT Bearer token
async def get_current_user(
    request: Request,
    x_api_key: Optional[str] = Security(api_key_header),
    auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth)
) -> dict:
    """
    Return: {"user_id": int}
    เส้นทาง Web: JWT Bearer token → decode `user_id` claim.
    (PRSC Portal v1 ยังไม่มี Discord bot — จึงไม่มี Discord path)
    """
    # กรณี System RPC: ผ่าน X-API-Key (สำหรับ script/automation ที่ไม่ใช่ user จริง)
    if x_api_key:
        if x_api_key == settings.API_KEY:
            return {"user_id": None, "is_system": True}
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # กรณี Web (SPA): JWT Bearer
    if auth:
        try:
            token = auth.credentials
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            user_id = payload.get("user_id")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid token: Missing user_id")
            return {"user_id": int(user_id), "is_system": False}
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    raise HTTPException(status_code=401, detail="Not authenticated: Bearer Token required")
