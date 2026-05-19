import asyncio
import httpx
from typing import List
import os

EMBEDDING_URL = os.getenv("EMBEDDING_URL")
EMBEDDING_URL_BATCH = os.getenv("EMBEDDING_URL_BATCH")

BATCH_SIZE = 32
MAX_CONCURRENCY = 5
MAX_RETRIES = 3
REQUEST_TIMEOUT = 120


def _chunk_list(items: List[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


async def _embed_batch(client: httpx.AsyncClient, texts: List[str]) -> List[List[float]]:
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.post(
                EMBEDDING_URL_BATCH,
                json={"texts": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["embeddings"]
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(2 ** attempt)


async def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []

    batches = list(_chunk_list(texts, BATCH_SIZE))

    limits = httpx.Limits(
        max_connections=50,
        max_keepalive_connections=20,
    )
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        limits=limits,
    ) as client:

        async def process_batch(batch: List[str]):
            async with semaphore:
                return await _embed_batch(client, batch)

        tasks = [process_batch(b) for b in batches]
        results = await asyncio.gather(*tasks)

    embeddings: List[List[float]] = []
    for r in results:
        embeddings.extend(r)

    return embeddings


async def embed_text(text: str) -> List[float]:
    # اگر خواستی، این را هم می‌توانی از /embed_batch استفاده کنی
    res = await embed_texts([text])
    return res[0]