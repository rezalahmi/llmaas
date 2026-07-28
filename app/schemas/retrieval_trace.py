"""Versioned, content-free contract for runtime retrieval facts.

This module defines the Phase 0 contract only. Emitting the contract from the
runtime retrieval pipeline belongs to Phase 2.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RetrievalStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


class RetrievalFailure(str, Enum):
    NO_CANDIDATES = "no_candidates"
    BELOW_RELEVANCE_THRESHOLD = "below_relevance_threshold"
    FILTER_ELIMINATED_ALL = "filter_eliminated_all"
    RERANKER_ELIMINATED_ALL = "reranker_eliminated_all"
    SOURCE_UNAVAILABLE = "source_unavailable"
    INDEX_UNAVAILABLE = "index_unavailable"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    UNKNOWN = "unknown"


class RetrievalStageName(str, Enum):
    QUERY_REWRITE = "query_rewrite"
    DENSE_RETRIEVAL = "dense_retrieval"
    FILTERING = "filtering"
    RERANKING = "reranking"
    CONTEXT_SELECTION = "context_selection"


class ConfidenceStatus(str, Enum):
    NOT_SUPPORTED = "not_supported"


class ContractModel(BaseModel):
    # JSON represents enum members as strings. Pydantic must deserialize those
    # strings while the generated JSON Schema enforces the wire-level types.
    model_config = ConfigDict(extra="forbid")


class RetrievedSource(ContractModel):
    source_id: str = Field(min_length=1, description="Opaque LLMaaS file identifier.")
    chunk_ref: str = Field(
        min_length=1,
        description="Stable, tenant-scoped, opaque chunk identifier.",
    )
    dense_rank: int | None = Field(
        ge=1,
        description="One-based rank returned by dense retrieval.",
    )
    dense_distance: float | None = Field(
        ge=0,
        description="Provider distance; lower is better. It is not confidence.",
    )
    dense_relevance_score: float | None = Field(
        description=(
            "Calibrated dense relevance only. It remains null until a named, "
            "versioned calibration is introduced."
        ),
    )
    rerank_rank: int | None = Field(
        ge=1,
        description="One-based rank after reranking; null when not reranked.",
    )
    rerank_score: float | None = Field(
        description=(
            "Raw provider reranker score with provider semantics; it is not a "
            "probability or answer confidence."
        ),
    )
    selected: bool = Field(
        description="True only when the chunk entered generation context."
    )


class RetrievalMetrics(ContractModel):
    candidate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    attempt_count: int = Field(
        ge=0,
        description="Number of retrieval attempts in this retrieval session.",
    )
    query_rewrite_count: int = Field(
        ge=0,
        description="Number of query rewrites; rewritten text is never included.",
    )
    latency_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def selected_does_not_exceed_candidates(self) -> "RetrievalMetrics":
        if self.selected_count > self.candidate_count:
            raise ValueError("selected_count cannot exceed candidate_count")
        return self


class RetrievalStage(ContractModel):
    stage: RetrievalStageName
    status: RetrievalStatus
    failure: RetrievalFailure | None

    @model_validator(mode="after")
    def failed_stage_has_failure(self) -> "RetrievalStage":
        if self.status == RetrievalStatus.FAILED and self.failure is None:
            raise ValueError("a failed stage must have a failure")
        if self.status == RetrievalStatus.NOT_REQUESTED and self.failure is not None:
            raise ValueError("a not_requested stage cannot have a failure")
        return self


class RetrievalVersions(ContractModel):
    retrieval_pipeline_version: str = Field(min_length=1)
    vector_index_provider: str = Field(min_length=1)
    vector_index_provider_version: str = Field(min_length=1)
    index_version: str | None
    corpus_revision: str | None
    embedding_model: str = Field(min_length=1)
    embedding_version: str = Field(min_length=1)
    query_rewriter_model: str | None
    query_rewriter_version: str | None
    reranker_model: str | None
    reranker_version: str | None
    chunking_strategy: str = Field(min_length=1)
    chunking_version: str = Field(min_length=1)
    generation_model: str = Field(min_length=1)
    generation_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def dependency_versions_are_complete(self) -> "RetrievalVersions":
        if self.index_version is None and self.corpus_revision is None:
            raise ValueError("index_version or corpus_revision must be set")
        if (self.query_rewriter_model is None) != (
            self.query_rewriter_version is None
        ):
            raise ValueError(
                "query_rewriter_model and query_rewriter_version must both be "
                "set or both be null"
            )
        if (self.reranker_model is None) != (self.reranker_version is None):
            raise ValueError(
                "reranker_model and reranker_version must both be set or both be null"
            )
        return self


class RetrievalConfidence(ContractModel):
    answer_confidence: None
    confidence_status: Literal[ConfidenceStatus.NOT_SUPPORTED]
    confidence_method: None
    calibration_version: None


class RetrievalTraceEvent(ContractModel):
    type: Literal["retrieval_trace"]
    schema_version: Literal["1.0"]
    trace_id: str = Field(
        min_length=1,
        pattern=r"^ragtrace_[A-Za-z0-9_-]+$",
        description=(
            "Opaque identifier for the entire retrieval session. It remains "
            "unchanged across attempts and query rewrites."
        ),
    )
    retrieval_status: RetrievalStatus
    retrieval_failure: RetrievalFailure | None
    vector_store_ids: list[str]
    stages: list[RetrievalStage]
    retrieved_sources: list[RetrievedSource]
    metrics: RetrievalMetrics
    versions: RetrievalVersions
    confidence: RetrievalConfidence

    @model_validator(mode="after")
    def enforce_event_invariants(self) -> "RetrievalTraceEvent":
        selected_sources = sum(source.selected for source in self.retrieved_sources)
        source_attributions = {
            (source.source_id, source.chunk_ref) for source in self.retrieved_sources
        }
        stage_names = {stage.stage for stage in self.stages}
        if len(source_attributions) != len(self.retrieved_sources):
            raise ValueError("source_id/chunk_ref attribution must be unique")
        if len(stage_names) != len(self.stages):
            raise ValueError("each retrieval stage may appear at most once")
        if self.metrics.candidate_count != len(self.retrieved_sources):
            raise ValueError(
                "candidate_count must equal the number of retrieved_sources"
            )
        if self.metrics.selected_count != selected_sources:
            raise ValueError(
                "selected_count must equal the number of selected sources"
            )
        if self.retrieval_status == RetrievalStatus.NOT_REQUESTED:
            if (
                self.retrieval_failure is not None
                or self.vector_store_ids
                or self.stages
                or self.retrieved_sources
                or self.metrics.attempt_count != 0
                or self.metrics.query_rewrite_count != 0
            ):
                raise ValueError(
                    "not_requested events cannot contain retrieval facts or failure"
                )
        elif self.metrics.attempt_count < 1:
            raise ValueError("requested retrieval sessions must have an attempt")
        if (
            self.retrieval_status == RetrievalStatus.COMPLETED
            and self.metrics.selected_count > 0
            and self.retrieval_failure is not None
        ):
            raise ValueError(
                "a completed event with selected context cannot have a failure"
            )
        if (
            self.retrieval_status == RetrievalStatus.FAILED
            and self.retrieval_failure is None
        ):
            raise ValueError("failed events must have a retrieval_failure")
        if self.retrieval_status == RetrievalStatus.FAILED and not any(
            stage.status == RetrievalStatus.FAILED for stage in self.stages
        ):
            raise ValueError("failed events must identify a failed stage")
        if self.retrieval_status == RetrievalStatus.DEGRADED and not any(
            stage.status in {RetrievalStatus.DEGRADED, RetrievalStatus.FAILED}
            for stage in self.stages
        ):
            raise ValueError("degraded events must identify a degraded/failed stage")
        return self
