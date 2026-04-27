# app\celery_app.py
from celery import Celery
from app.config import REDIS_URL

celery = Celery(
    "llm",
    broker=f"{REDIS_URL}/0",
    backend=f"{REDIS_URL}/1"
)