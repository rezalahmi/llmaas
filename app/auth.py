# app\auth.py
from fastapi import Header, HTTPException, Depends
from app.redis_client import get_redis
import redis.asyncio as redis
import json
from app.config import settings

async def get_api_key(
    authorization: str = Header(...),
    r = Depends(get_redis)
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")

    key = authorization.split()[1]

    data = await r.get(f"api_key:{key}")
    if not data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return json.loads(data)