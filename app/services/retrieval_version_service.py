"""Validated identity/version configuration for retrieval dependencies."""

import os
from dataclasses import asdict, dataclass

from app.config import settings


INVALID_VERSION_VALUES = {"", "unknown", "unversioned"}
PRODUCTION_ENVIRONMENTS = {"production", "stage", "staging"}


@dataclass(frozen=True)
class RetrievalDependencyVersions:
    embedding_model: str
    embedding_version: str
    reranker_model: str
    reranker_version: str
    chunking_strategy: str
    chunking_version: str
    generation_model: str
    generation_version: str
    vector_index_provider: str
    vector_index_version: str

    def validate(self, *, production: bool) -> "RetrievalDependencyVersions":
        values = asdict(self)
        invalid = [
            name
            for name, value in values.items()
            if not value.strip()
            or (production and value.strip().lower() in INVALID_VERSION_VALUES)
        ]
        if invalid:
            raise RuntimeError(
                "Missing or invalid retrieval dependency identity: "
                + ", ".join(sorted(invalid))
            )
        return self


def get_retrieval_dependency_versions(
    *, production: bool | None = None
) -> RetrievalDependencyVersions:
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    is_production = (
        environment in PRODUCTION_ENVIRONMENTS if production is None else production
    )

    default_generation_model = settings.DEFAULT_MODEL
    default_generation_version = "model-tag-v1"
    if ":" in settings.DEFAULT_MODEL:
        default_generation_model, default_generation_version = (
            settings.DEFAULT_MODEL.rsplit(":", 1)
        )

    def configured(name: str, code_default: str | None) -> str:
        return os.getenv(name) or code_default or ""

    versions = RetrievalDependencyVersions(
        embedding_model=configured("EMBEDDING_MODEL", settings.EMBEDDING_MODEL),
        embedding_version=configured(
            "EMBEDDING_MODEL_VERSION",
            settings.EMBEDDING_MODEL_VERSION,
        ),
        reranker_model=configured("RERANKER_MODEL", settings.RERANKER_MODEL),
        reranker_version=configured(
            "RERANKER_MODEL_VERSION",
            settings.RERANKER_MODEL_VERSION,
        ),
        chunking_strategy=configured(
            "CHUNKING_STRATEGY",
            settings.CHUNKING_STRATEGY,
        ),
        chunking_version=configured(
            "CHUNKING_VERSION",
            settings.CHUNKING_VERSION,
        ),
        generation_model=configured(
            "GENERATION_MODEL",
            settings.GENERATION_MODEL or default_generation_model,
        ),
        generation_version=configured(
            "GENERATION_MODEL_VERSION",
            settings.GENERATION_MODEL_VERSION or default_generation_version,
        ),
        vector_index_provider=configured(
            "VECTOR_INDEX_PROVIDER",
            settings.VECTOR_INDEX_PROVIDER,
        ),
        vector_index_version=configured(
            "VECTOR_INDEX_VERSION",
            settings.VECTOR_INDEX_VERSION,
        ),
    )
    return versions.validate(production=is_production)
