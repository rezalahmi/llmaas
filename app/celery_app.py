# app\celery_app.py
from celery import Celery
from app.config import settings

celery = Celery(
    "llm",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.autodiscover_tasks(["app"])

