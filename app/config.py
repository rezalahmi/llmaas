# app\config.py
from pydantic_settings import BaseSettings
from typing import ClassVar

class Settings(BaseSettings):
    REDIS_URL: str="redis://localhost:6379/0"
    CELERY_BROKER_URL: str="redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str="redis://localhost:6379/2"

    OLLAMA_URL: str = "http://localhost:11434"
    DEFAULT_MODEL: str = "gemma4:e4b"

    class Config:
        env_file = ".env"


settings = Settings()

