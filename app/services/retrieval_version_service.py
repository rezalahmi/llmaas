"""Validated identity/version configuration for retrieval dependencies."""

import os
from dataclasses import asdict, dataclass


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

    def configured(name: str, development_default: str) -> str:
        return os.getenv(name, "" if is_production else development_default)

    versions = RetrievalDependencyVersions(
        embedding_model=configured("EMBEDDING_MODEL", "embedding-service"),
        embedding_version=configured("EMBEDDING_MODEL_VERSION", "dev-1"),
        reranker_model=configured("RERANKER_MODEL", "reranker-service"),
        reranker_version=configured("RERANKER_MODEL_VERSION", "dev-1"),
        chunking_strategy=configured(
            "CHUNKING_STRATEGY", "recursive_character"
        ),
        chunking_version=configured("CHUNKING_VERSION", "1"),
        generation_model=configured("GENERATION_MODEL", "gemma4:e4b"),
        generation_version=configured("GENERATION_MODEL_VERSION", "dev-1"),
        vector_index_provider=configured("VECTOR_INDEX_PROVIDER", "chroma"),
        vector_index_version=configured("VECTOR_INDEX_VERSION", "dev-1"),
    )
    return versions.validate(production=is_production)
