# app/services/usage_service.py

from app.repositories.usage_repository import get_total_usage_from_db

async def get_user_usage_service(pg, redis, *, user_id: int):
    # ۱. سعی کن از Redis بخوانی (Fast Path)
    redis_key = f"usage:{user_id}"
    cached_usage = await redis.get(redis_key)
    
    if cached_usage:
        return int(cached_usage)

    # ۲. اگر در Redis نبود (Cache Miss)، از DB بخوان
    db_usage = await get_total_usage_from_db(pg, user_id=user_id)
    
    # ۳. پر کردن دوباره Redis (Backfill) برای دفعات بعدی
    await redis.set(redis_key, db_usage)
    
    return db_usage


async def get_admin_user_usage_service(conn, redis, *, user_id: int):
    redis_key = f"usage:{user_id}"

    cached_usage = await redis.get(redis_key)

    if cached_usage is not None:
        tokens_used = int(cached_usage)
    else:
        row = await conn.fetchrow(
            """
            SELECT last_total
            FROM user_usage_snapshot
            WHERE external_user_id = $1
            """,
            user_id,
        )

        tokens_used = int(row["last_total"]) if row else 0

    quota_row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total_keys,
            COUNT(*) FILTER (WHERE is_active = true) AS active_keys,
            COALESCE(SUM(quota), 0) AS quota_remaining
        FROM api_keys
        WHERE external_user_id = $1
        """,
        user_id,
    )

    return {
        "user_id": user_id,
        "tokens_used": tokens_used,
        "quota_remaining": int(quota_row["quota_remaining"] or 0),
        "total_keys": int(quota_row["total_keys"] or 0),
        "active_keys": int(quota_row["active_keys"] or 0),
    }
