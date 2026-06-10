import os
import asyncio
import asyncpg
import redis.asyncio as redis
from datetime import date
import logging

# ---------- Logging ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("usage-sync")

# ---------- Config ----------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL")
BATCH_SIZE = int(os.getenv("USAGE_SYNC_BATCH_SIZE", "500"))
KEY_PATTERN = "usage:*"

async def process_batch(conn, r, keys):
    # Pipeline برای دریافت همه مقادیر از Redis
    pipe = r.pipeline()
    for k in keys:
        pipe.get(k)
    values = await pipe.execute()

    today = date.today()
    user_ids = [int(k.split(":")[1]) for k in keys]

    # یک بار fetch کردن همه snapshotها برای این batch
    rows = await conn.fetch(
        "SELECT external_user_id, last_total FROM user_usage_snapshot WHERE external_user_id = ANY($1::bigint[])",
        user_ids
    )
    snapshots = {r["external_user_id"]: r["last_total"] for r in rows}

    processed, updated, skipped, resets = 0, 0, 0, 0

    for key, val in zip(keys, values):
        if val is None:
            continue

        external_user_id = int(key.split(":")[1])
        redis_total = int(val)
        last_total = snapshots.get(external_user_id, 0)
        delta = redis_total - last_total

        if delta < 0:
            resets += 1
            logger.warning(f"RESET user={external_user_id}: redis={redis_total} < last={last_total}")
            await conn.execute(
                "INSERT INTO user_usage_snapshot (external_user_id, last_total) VALUES ($1, $2) ON CONFLICT (external_user_id) DO UPDATE SET last_total = EXCLUDED.last_total, updated_at = now()",
                external_user_id, redis_total
            )
        elif delta == 0:
            skipped += 1
            continue
        else:
            updated += 1
            logger.info(f"UPDATE daily user={external_user_id} add_delta={delta}")
            # آپدیت روزانه
            await conn.execute(
                "INSERT INTO user_daily_usage (external_user_id, usage_date, total_tokens) VALUES ($1, $2, $3) ON CONFLICT (external_user_id, usage_date) DO UPDATE SET total_tokens = user_daily_usage.total_tokens + EXCLUDED.total_tokens",
                external_user_id, today, delta
            )
            # آپدیت اسنپ‌شات
            await conn.execute(
                "INSERT INTO user_usage_snapshot (external_user_id, last_total) VALUES ($1, $2) ON CONFLICT (external_user_id) DO UPDATE SET last_total = EXCLUDED.last_total, updated_at = now()",
                external_user_id, redis_total
            )
        processed += 1

    logger.info(f"Batch done: processed={processed}, updated={updated}, skipped={skipped}, resets={resets}")

async def main():
    logger.info("Starting usage sync...")
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pool = await asyncpg.create_pool(DATABASE_URL)

    # استفاده از 0 عددی برای سازگاری بهتر
    cursor = 0 
    
    async with pool.acquire() as conn:
        # تنظیم timeout برای جلوگیری از قفل شدن نامحدود
        await conn.execute("SET statement_timeout = '30s'")
        
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=KEY_PATTERN, count=BATCH_SIZE)
            
            if keys:
                logger.info(f"Processing batch of {len(keys)} keys")
                async with conn.transaction():
                    await process_batch(conn, r, keys)
            
            # خروج امن با تبدیل به int
            if int(cursor) == 0:
                break

    await r.aclose()
    await pool.close()
    logger.info("Usage sync finished.")

if __name__ == "__main__":
    asyncio.run(main())
