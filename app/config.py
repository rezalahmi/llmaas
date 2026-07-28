# app\config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from importlib.metadata import PackageNotFoundError, version


def installed_package_version(package: str, fallback: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return fallback


CHROMA_CLIENT_VERSION = installed_package_version(
    "chromadb",
    "client-api-v1",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    # Retrieval dependency identity. Environment variables with these names
    # remain optional overrides; defaults describe the implementation in this
    # repository and are deliberately versioned rather than "unversioned".
    EMBEDDING_MODEL: str = "embedding-service"
    EMBEDDING_MODEL_VERSION: str = "http-api-v1"
    RERANKER_MODEL: str = "reranker-service"
    RERANKER_MODEL_VERSION: str = "http-api-v1"
    CHUNKING_STRATEGY: str = "recursive_character"
    CHUNKING_VERSION: str = "1"
    GENERATION_MODEL: Optional[str] = None
    GENERATION_MODEL_VERSION: Optional[str] = None
    VECTOR_INDEX_PROVIDER: str = "chroma"
    VECTOR_INDEX_VERSION: str = CHROMA_CLIENT_VERSION

    def model_post_init(self, __context):
        # اگر celery تنظیم نشده باشد از redis استفاده کن
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL

        if not self.CELERY_RESULT_BACKEND:
            # نتیجه‌ها بهتر است DB جدا داشته باشند
            self.CELERY_RESULT_BACKEND = self.REDIS_URL.replace("/0", "/1")


settings = Settings()
