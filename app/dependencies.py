# app\dependencies.py
import redis
import json
from fastapi import Header, HTTPException, Depends, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.redis_client import get_redis
from app.config import settings
import os
import logging

logger = logging.getLogger(__name__)

# تعریف ابزار امنیتی Bearer
security = HTTPBearer()



async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    r = Depends(get_redis)
):
    # مقدار توکن از هدر Authorization: Bearer <TOKEN> استخراج می‌شود
    token = credentials.credentials
    
    # جستجو در Redis با استفاده از توکن استخراج شده
    data = await r.get(f"api_key:{token}")
    
    if not data:
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return json.loads(data)


async def verify_admin(x_admin_key: str = Header(None)):
    admin_secret = settings.ADMIN_SECRET
    print(f"x_admin_key {x_admin_key} and ADMIN_SECRET {admin_secret}")
    if x_admin_key != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key."
        )