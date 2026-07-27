# app\tasks.py
from app.celery_app import celery
import requests
from app.config import settings

@celery.task
def generate_task(payload):
    resp = requests.post(settings.OLLAMA_URL, json=payload, timeout=300)

    if resp.status_code != 200:
        raise Exception(f"Upstream error {resp.status_code}: {resp.text[:500]}")

    try:
        data = resp.json()
    except ValueError:
        raise Exception(f"Invalid JSON from upstream: {resp.text[:500]}")
    return data


@celery.task
def tools_calling_task(payload):
    print(f"DEBUG: tasks: PAYLOAD TYPE {type(payload)}")
    resp = requests.post(settings.OLLAMA_TOOLS_URL, json=payload, timeout=300)

    if resp.status_code != 200:
        raise Exception(f"Upstream error {resp.status_code}: {resp.text[:500]}")

    try:
        data = resp.json()
    except ValueError:
        raise Exception(f"Invalid JSON from upstream: {resp.text[:500]}")
    return data


@celery.task(
    name="semantic_coverage_evaluation",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def semantic_coverage_evaluation_task(run_id: str):
    import asyncio
    import os

    import asyncpg

    from app.services.semantic_coverage_service import (
        run_semantic_coverage_evaluation,
    )

    async def execute():
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://appuser:apppass@postgres:5432/appdb",
        )
        connection = await asyncpg.connect(database_url)
        try:
            await run_semantic_coverage_evaluation(
                connection, run_id=run_id
            )
        finally:
            await connection.close()

    asyncio.run(execute())
    return {"run_id": run_id, "status": "processed"}
