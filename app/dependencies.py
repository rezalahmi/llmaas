# app\dependencies.py
import redis
import json
from fastapi import Header, HTTPException, Depends, status
from app.redis_client import get_redis
from app.config import settings
import os
import logging

logger = logging.getLogger(__name__)





async def get_current_user(x_api_key: str = Header(...),
                     r = Depends(get_redis)):
    data =  await r.get(f"api_key:{x_api_key}")
    if not data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return json.loads(data)


async def verify_admin(x_admin_key: str = Header(None)):
    admin_secret = settings.ADMIN_SECRET
    print(f"x_admin_key {x_admin_key} and ADMIN_SECRET {admin_secret}")
    if x_admin_key != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key."
        )