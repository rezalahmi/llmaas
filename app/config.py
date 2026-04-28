# app\config.py
from pydantic import BaseSettings


class Settings(BaseSettings):
    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # Ollama
    OLLAMA_URL: str = "http://host.docker.internal:11434"
    DEFAULT_MODEL: str = "gemma4:e4b"

    # عمومی
    ENV: str = "development"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
