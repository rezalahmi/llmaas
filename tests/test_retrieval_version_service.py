import pytest

from app.services.retrieval_version_service import (
    get_retrieval_dependency_versions,
)


VERSION_ENV = {
    "EMBEDDING_MODEL": "embed-x",
    "EMBEDDING_MODEL_VERSION": "3",
    "RERANKER_MODEL": "rerank-y",
    "RERANKER_MODEL_VERSION": "2",
    "CHUNKING_STRATEGY": "recursive_character",
    "CHUNKING_VERSION": "5",
    "GENERATION_MODEL": "model-z",
    "GENERATION_MODEL_VERSION": "1",
    "VECTOR_INDEX_PROVIDER": "chroma",
    "VECTOR_INDEX_VERSION": "0.6",
}


def test_production_rejects_unversioned_dependency(monkeypatch):
    for name, value in VERSION_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("EMBEDDING_MODEL_VERSION", "unversioned")
    with pytest.raises(RuntimeError, match="embedding_version"):
        get_retrieval_dependency_versions(production=True)


def test_production_uses_central_code_defaults_when_env_is_missing(monkeypatch):
    for name in VERSION_ENV:
        monkeypatch.delenv(name, raising=False)
    versions = get_retrieval_dependency_versions(production=True)
    assert versions.embedding_model == "embedding-service"
    assert versions.embedding_version == "http-api-v1"
    assert versions.reranker_model == "reranker-service"
    assert versions.chunking_strategy == "recursive_character"
    assert versions.generation_model == "gemma4"
    assert versions.generation_version == "e4b"
    assert versions.vector_index_provider == "chroma"
    assert versions.vector_index_version


def test_production_accepts_complete_version_contract(monkeypatch):
    for name, value in VERSION_ENV.items():
        monkeypatch.setenv(name, value)
    versions = get_retrieval_dependency_versions(production=True)
    assert versions.embedding_model == "embed-x"
    assert versions.vector_index_version == "0.6"
