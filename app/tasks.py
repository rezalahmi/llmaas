# app\tasks.py
from app.celery_app import celery
import requests
from app.config import settings

@celery.task
def generate_task(payload):
    r = requests.post(settings.OLLAMA_URL, json=payload, timeout=300)
    return r.json()