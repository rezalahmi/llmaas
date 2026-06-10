import asyncio
import json
import hashlib
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as redis


import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://appuser:apppass@postgres:5432/appdb"
)


def sha256_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def ts_to_datetime(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc)


async def scan(r, pattern):

    cursor = 0

    while True:

        cursor, keys = await r.scan(cursor, match=pattern, count=500)

        for k in keys:
            yield k

        if cursor == 0:
            break


async def migrate_api_keys(r, pg):

    user_to_api = {}

    async for key in scan(r, "api_key:*"):

        api_key = key.split(":", 1)[1]

        raw = await r.get(key)

        data = json.loads(raw)

        user_id = int(data["user_id"])

        row = await pg.fetchrow(
            """
            INSERT INTO public.api_keys
            (external_user_id,user_name,key_prefix,key_hash,quota)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (key_hash)
            DO UPDATE SET quota=EXCLUDED.quota
            RETURNING id
            """,
            user_id,
            data.get("user"),
            api_key[:12],
            sha256_text(api_key),
            int(data.get("quota", 0)),
        )

        user_to_api[user_id] = row["id"]

    return user_to_api


async def migrate_files(r, pg, user_map):

    async for key in scan(r, "file:*"):

        file_id = key.split(":", 1)[1]

        data = await r.hgetall(key)

        user_id = int(data["user_id"])

        filename = data["filename"]

        ext = filename.split(".")[-1]

        bytes_ = int(data["bytes"])

        path = data["path"]

        created = ts_to_datetime(data["created_at"])

        await pg.execute(
            """
            INSERT INTO public.files
            (
                id,
                external_user_id,
                api_key_id,
                filename,
                ext,
                bytes,
                storage_backend,
                storage_key,
                storage_path,
                status,
                created_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,'disk',$7,$8,'ready',$9)
            ON CONFLICT (id) DO NOTHING
            """,
            file_id,
            user_id,
            user_map.get(user_id),
            filename,
            ext,
            bytes_,
            file_id,
            path,
            created,
        )


async def migrate_vector_stores(r, pg, user_map):

    async for key in scan(r, "vector_store:*"):

        vs_id = key.split(":", 1)[1]

        data = await r.hgetall(key)

        user_id = int(data["user_id"])

        created = ts_to_datetime(data["created_at"])

        await pg.execute(
            """
            INSERT INTO public.vector_stores
            (
                id,
                external_user_id,
                api_key_id,
                name,
                collection_name,
                storage_backend,
                status,
                created_at
            )
            VALUES ($1,$2,$3,$4,$5,'chroma','ready',$6)
            ON CONFLICT (id) DO NOTHING
            """,
            vs_id,
            user_id,
            user_map.get(user_id),
            data.get("name"),
            vs_id,
            created,
        )


async def migrate_vector_store_files(r, pg, user_map):

    async for key in scan(r, "vector_store_file:*"):

        data = await r.hgetall(key)

        status = data.get("status")

        if status == "completed":
            status = "ready"

        created = ts_to_datetime(data["created_at"])

        await pg.execute(
            """
            INSERT INTO public.vector_store_files
            (
                id,
                vector_store_id,
                file_id,
                status,
                created_at
            )
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (id) DO NOTHING
            """,
            data["id"],
            data["vector_store_id"],
            data["file_id"],
            status,
            created,
        )


async def main():

    r = redis.from_url(REDIS_URL, decode_responses=True)

    pg = await asyncpg.connect(POSTGRES_DSN)

    db_name = await pg.fetchval("SELECT current_database()")
    search_path = await pg.fetchval("SHOW search_path")
    print(f"DEBUG: Connected to database: {db_name}")
    print(f"DEBUG: Current search path: {search_path}")

    print("Migrating api_keys")
    user_map = await migrate_api_keys(r, pg)

    print("Migrating files")
    await migrate_files(r, pg, user_map)

    print("Migrating vector_stores")
    await migrate_vector_stores(r, pg, user_map)

    print("Migrating vector_store_files")
    await migrate_vector_store_files(r, pg, user_map)

    await pg.close()
    await r.close()


asyncio.run(main())
