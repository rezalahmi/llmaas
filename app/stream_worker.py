# app\stream_worker.py
import asyncio
import json
import httpx
import redis.asyncio as redis
from app.config import REDIS_URL, OLLAMA_URL
from app.redis_client import get_redis

async def run():
    r = get_redis()

    while True:
        _, raw = await r.brpop("stream_queue")

        data = json.loads(raw)
        request_id = data["request_id"]
        payload = data["payload"]

        payload["stream"] = True

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", OLLAMA_URL, json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue

                    await r.publish(
                        f"stream:{request_id}",
                        line
                    )

        await r.publish(f"stream:{request_id}", "[DONE]")


if __name__ == "__main__":
    asyncio.run(run())