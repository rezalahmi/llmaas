"""Build the content-free Phase 2 retrieval trace from runtime facts."""

import uuid

from app.schemas.file_search import FileSearchResponse
from app.schemas.retrieval_trace import (
    RetrievalConfidence,
    RetrievalMetrics,
    RetrievalStage,
    RetrievalTraceEvent,
    RetrievalVersions,
    RetrievedSource,
)
from app.services.retrieval_version_service import (
    get_retrieval_dependency_versions,
)


def _runtime_generation_identity(model: str) -> tuple[str, str]:
    if ":" in model:
        name, version = model.rsplit(":", 1)
        if name and version:
            return name, version
    # The request value is the authoritative runtime identity. A provider that
    # does not expose a separate revision uses the complete model tag as both.
    return model, model


def build_retrieval_trace(
    *,
    fs_response: FileSearchResponse,
    vector_store_ids: list[str],
    generation_model: str,
    trace_id: str | None = None,
) -> RetrievalTraceEvent:
    runtime = fs_response.retrieval_runtime
    dependencies = get_retrieval_dependency_versions()
    generation_name, generation_version = _runtime_generation_identity(
        generation_model
    )

    sources = [
        RetrievedSource(
            source_id=fact.source_id,
            chunk_ref=fact.chunk_ref,
            dense_rank=fact.dense_rank,
            dense_distance=fact.dense_distance,
            dense_relevance_score=None,
            rerank_rank=fact.rerank_rank,
            rerank_score=fact.rerank_score,
            selected=fact.selected,
        )
        for fact in fs_response.retrieval_facts
    ]
    stages = [
        RetrievalStage(stage=name, **runtime["stages"][name])
        for name in (
            "query_rewrite",
            "dense_retrieval",
            "filtering",
            "reranking",
            "context_selection",
        )
    ]

    return RetrievalTraceEvent(
        type="retrieval_trace",
        schema_version="1.0",
        trace_id=trace_id or f"ragtrace_{uuid.uuid4().hex}",
        retrieval_status=runtime["retrieval_status"],
        retrieval_failure=runtime["retrieval_failure"],
        vector_store_ids=vector_store_ids,
        stages=stages,
        retrieved_sources=sources,
        metrics=RetrievalMetrics(
            candidate_count=len(sources),
            selected_count=sum(source.selected for source in sources),
            attempt_count=runtime["attempt_count"],
            query_rewrite_count=runtime["query_rewrite_count"],
            latency_ms=runtime["latency_ms"],
        ),
        versions=RetrievalVersions(
            retrieval_pipeline_version="1",
            vector_index_provider=dependencies.vector_index_provider,
            vector_index_provider_version=dependencies.vector_index_version,
            index_version=dependencies.vector_index_version,
            corpus_revision=None,
            embedding_model=dependencies.embedding_model,
            embedding_version=dependencies.embedding_version,
            query_rewriter_model=None,
            query_rewriter_version=None,
            reranker_model=dependencies.reranker_model,
            reranker_version=dependencies.reranker_version,
            chunking_strategy=dependencies.chunking_strategy,
            chunking_version=dependencies.chunking_version,
            generation_model=generation_name,
            generation_version=generation_version,
        ),
        confidence=RetrievalConfidence(
            answer_confidence=None,
            confidence_status="not_supported",
            confidence_method=None,
            calibration_version=None,
        ),
    )
