# app/repositories/usage_repository.py

async def get_total_usage_from_db(pg, *, user_id: int):
    # گرفتن آخرین مقدار از Snapshot که سریع‌ترین راه است
    row = await pg.fetchrow(
        "SELECT last_total FROM user_usage_snapshot WHERE external_user_id = $1",
        user_id
    )
    return row["last_total"] if row else 0

async def get_daily_usage_history(pg, *, user_id: int, days: int = 30):
    # گرفتن تاریخچه برای رسم نمودار (مثلاً ۳۰ روز اخیر)
    return await pg.fetch(
        """
        SELECT usage_date, total_tokens 
        FROM user_daily_usage 
        WHERE external_user_id = $1 
        ORDER BY usage_date DESC LIMIT $2
        """,
        user_id, days
    )
