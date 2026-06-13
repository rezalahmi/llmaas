from fastapi import Header, HTTPException, Depends
from app.redis_client import get_redis
from app.postgres_client import get_pg
from app.security.api_keys import hash_api_key
import json
from datetime import datetime, timezone


async def get_api_key(
    authorization: str = Header(...),
    r = Depends(get_redis),
    pg = Depends(get_pg)
):

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")

    parts = authorization.split()

    if len(parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid auth header")
    
    raw_key = parts[1]
    key_hash = hash_api_key(raw_key)

    row = await pg.fetchrow(
         """
        select id, external_user_id, user_name, quota, is_active, expires_at
        from api_keys
        where key_hash = $1
        limit 1
        """,
        key_hash,
    )
    
    if row:
        # 1. چک کردن is_active
        if not row["is_active"]:
            raise HTTPException(status_code=401, detail="Inactive API key")
        # 2. چک کردن expires_at
        expires_at = row["expires_at"]
        # اگر expires_at تنظیم شده و از الان گذشته، خطا بده
        if expires_at and expires_at < datetime.now(timezone.utc): # از datetime.now(timezone.utc) استفاده کن
            raise HTTPException(status_code=401, detail="API key expired") # یا 403 Forbidden
         # 3. چک کردن quota (هم از DB و هم از Redis)
        if row["quota"] <= 0:
            raise HTTPException(status_code=402, detail="Quota exceeded")
        
        user = {
            "key_id": row["id"],
            "user_id": row["external_user_id"],
            "user": row["user_name"],
            "quota": row["quota"],
            "source": "postgres",
        }
        # used = await r.get(f"usage:{user['user_id']}")
        # used = int(used or 0)

        # if used >= user["quota"]:
        #     raise HTTPException(status_code=402, detail="Quota exceeded")

        await pg.execute(
            """
            update api_keys
            set last_used_at = now()
            where id = $1
            """,
            row["id"],
        )

        return user

    # Temporary fallback برای کلیدهای قدیمی داخل Redis
    data = await r.get(f"api_key:{raw_key}")

    if not data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if isinstance(data, bytes):
        data = data.decode("utf-8")

    user = json.loads(data)
    user["source"] = "redis_legacy"

    used = await r.get(f"usage:{user['user_id']}")
    used = int(used or 0)

    if used >= user["quota"]:
        raise HTTPException(status_code=402, detail="Quota exceeded")

    return user
