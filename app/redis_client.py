# app\redis_client.py
import redis.asyncio as redis
from app.config import settings

# استفاده از یک متغیر داخلی برای کلاینت
_redis_client = None

def get_redis_connection():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            # این دو پارامتر برای رفع مشکل Timeout حیاتی هستند
            socket_connect_timeout=10,
            socket_timeout=None,  # بی نهایت منتظر بماند
            max_connections=50
        )
    return _redis_client

async def get_redis():
    return get_redis_connection()

async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None

