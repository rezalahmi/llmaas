# app/services/embedding_service.py

import httpx
import os
import asyncio

EMBEDDING_URL = os.getenv("EMBEDDING_URL")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed multiple texts in parallel.
    Returns list of embedding vectors.
    """

    if not texts:
        return []

    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [
            client.post(EMBEDDING_URL, json={"text": t})
            for t in texts
        ]

        responses = await asyncio.gather(*tasks)

    embeddings = []
    for r in responses:
        r.raise_for_status()
        embeddings.append(r.json()["embedding"])

    return embeddings


async def embed_text(text: str) -> list[float]:
    """
    Embed a single text.
    """
    embeddings = await embed_texts([text])
    return embeddings[0]
