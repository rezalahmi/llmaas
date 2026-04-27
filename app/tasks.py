# app\tasks.py
from app.celery_app import celery
import requests
from app.config import OLLAMA_URL

@celery.task
def generate_task(payload):
    r = requests.post(OLLAMA_URL, json=payload, timeout=300)
    return r.json()