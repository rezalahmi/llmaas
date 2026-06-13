# app/services/admin_usage_service.py

async def get_admin_user_usage_service(pg_pool, redis, *, user_id: int):
    redis_key = f"usage:{user_id}"

    cached_usage = await redis.get(redis_key)

    if cached_usage is not None:
        tokens_used = int(cached_usage)
    else:
        async with pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT last_total
                FROM user_usage_snapshot
                WHERE external_user_id = $1
                """,
                user_id,
            )
        tokens_used = int(row["last_total"]) if row else 0

    async with pg_pool.acquire() as conn:
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
