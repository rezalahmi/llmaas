# app\dependencies.py
import redis
import json
from fastapi import Header, HTTPException, Depends, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.redis_client import get_redis
from app.config import settings
import hashlib
import logging

from app.postgres_client import get_pg

logger = logging.getLogger(__name__)

# تعریف ابزار امنیتی Bearer
security = HTTPBearer()



def hash_token(token: str) -> str:
    """هش کردن توکن برای مقایسه با دیتابیس"""
    return hashlib.sha256(token.encode()).hexdigest()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    pg = Depends(get_pg)
):
    token = credentials.credentials
    token_hash = hash_token(token)

    # جستجو در دیتابیس به جای Redis
    # از هشِ کلید استفاده می‌کنیم
    query = """
    SELECT id, external_user_id, user_name, quota 
    FROM api_keys 
    WHERE key_hash = $1 AND is_active = true
    """
    
    user_record = await pg.fetchrow(query, token_hash)
    
    if not user_record:
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # اختیاری: آپدیت کردن last_used_at در دیتابیس
    # این کار برای مانیتورینگ عالی است
    await pg.execute(
        "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1", 
        user_record['id']
    )

    # تبدیل رکورد دیتابیس به دیکشنری برای استفاده در بقیه سرویس‌ها
    return dict(user_record)

async def verify_admin(x_admin_key: str = Header(None)):
    admin_secret = settings.ADMIN_SECRET
    print(f"x_admin_key {x_admin_key} and ADMIN_SECRET {admin_secret}")
    if x_admin_key != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key."
        )