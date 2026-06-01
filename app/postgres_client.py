# app/postgres_client.py

import os
import asyncpg

_pool = None


async def connect_postgres():
    global _pool

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://appuser:apppassword@postgres:5432/appdb"
    )

    _pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=10,
    )


async def close_postgres():
    global _pool

    if _pool:
        await _pool.close()
        _pool = None


async def get_pg():
    if _pool is None:
        raise RuntimeError("Postgres pool is not initialized")

    async with _pool.acquire() as conn:
        yield conn
