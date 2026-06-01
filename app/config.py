# app\config.py
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Security
    ADMIN_SECRET: Optional[str] = None
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # Ollama
    OLLAMA_URL: str = "http://host.docker.internal:11434/api/generate"
    OLLAMA_TOOLS_URL: str = "http://host.docker.internal:11434/api/chat"
    RERANKER_URL: str = "http://host.docker.internal:9100/rerank"

    # Model
    DEFAULT_MODEL: str = "gemma4:e4b"

    class Config:
        env_file = ".env"
        extra = "ignore"

    def model_post_init(self, __context):
        # اگر celery تنظیم نشده باشد از redis استفاده کن
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL

        if not self.CELERY_RESULT_BACKEND:
            # نتیجه‌ها بهتر است DB جدا داشته باشند
            self.CELERY_RESULT_BACKEND = self.REDIS_URL.replace("/0", "/1")


settings = Settings()
