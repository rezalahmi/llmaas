# app\rate_limit.py
import time
from fastapi import HTTPException

async def check_rate_limit(r, user_id: str, limit: int):
    now = int(time.time())
    window = now // 60

    key = f"rate:{user_id}:{window}"

    async with r.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, 60)
        count, _ = await pipe.execute()

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded"
        )
