# app\celery_app.py
from celery import Celery
from app.config import settings

celery = Celery(
    "llm",
    broker=f"{settings.REDIS_URL}/0",
    backend=f"{settings.REDIS_URL}/1"
)