# app\llm\ollama_client.py
import httpx
from app.config import settings

async def generate(payload):
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(settings.OLLAMA_URL, json=payload)
        return r.json()