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
