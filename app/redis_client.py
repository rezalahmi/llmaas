# app\redis_client.py
import redis.asyncio as redis
from app.config import settings

redis_client: redis.Redis | None = None

async def get_redis():
    return redis_client

async def init_redis():
    global redis_client
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50
    )

async def close_redis():
    await redis_client.close()




