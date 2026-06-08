import asyncio
import json
import os
import hashlib

import asyncpg
import redis.asyncio as redis


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_prefix(api_key: str, length: int = 12) -> str:
    return api_key[:length]


async def main():
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://appuser:apppassword@postgres:5432/appdb"
    )

    r = redis.from_url(redis_url)
    pg = await asyncpg.connect(database_url)

    keys = await r.keys("api_key:*")

    migrated = 0
    skipped = 0

    for redis_key in keys:
        if isinstance(redis_key, bytes):
            redis_key = redis_key.decode("utf-8")

        raw_api_key = redis_key.replace("api_key:", "", 1)

        data = await r.get(redis_key)

        if not data:
            skipped += 1
            continue

        if isinstance(data, bytes):
            data = data.decode("utf-8")

        payload = json.loads(data)

        user_id = payload.get("user_id")
        user_name = payload.get("user")
        quota = payload.get("quota", 0)

        key_hash = hash_api_key(raw_api_key)
        key_prefix = api_key_prefix(raw_api_key)

        await pg.execute(
            """
            insert into api_keys (
                external_user_id,
                user_name,
                key_prefix,
                key_hash,
                quota,
                is_active
            )
            values ($1, $2, $3, $4, $5, true)
            on conflict (key_hash) do update set
                external_user_id = excluded.external_user_id,
                user_name = excluded.user_name,
                key_prefix = excluded.key_prefix,
                quota = excluded.quota,
                is_active = true
            """,
            user_id,
            user_name,
            key_prefix,
            key_hash,
            quota,
        )

        migrated += 1

    await pg.close()
    await r.close()

    print({
        "migrated": migrated,
        "skipped": skipped,
    })


if __name__ == "__main__":
    asyncio.run(main())
