# app\dependencies.py
import redis
import json
from fastapi import Header, HTTPException, Depends
from app.redis_client import get_redis



async def get_current_user(x_api_key: str = Header(...),
                     r = Depends(get_redis)):
    data =  await r.get(f"api_key:{x_api_key}")
    if not data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return json.loads(data)
