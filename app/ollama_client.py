# app\ollama_client.py
import httpx
from app.config import OLLAMA_URL

async def generate(payload):
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(OLLAMA_URL, json=payload)
        return r.json()