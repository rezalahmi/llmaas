from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class EvaluationCaseCreate(BaseModel):
    query: str = Field(min_length=2)
    gold_chunk_ids: list[str] = Field(min_length=1)
    paraphrases: list[str] = Field(default_factory=list)
    language: str | None = Field(default=None, max_length=32)
    intent: str | None = Field(default=None, max_length=100)
    rarity: str | None = Field(default=None, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return value.strip()

    @field_validator("gold_chunk_ids")
    @classmethod
    def unique_gold_chunks(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not normalized:
            raise ValueError("gold_chunk_ids must contain at least one chunk id")
        return normalized


class EvaluationDatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    version: int = Field(default=1, ge=1)
    cases: list[EvaluationCaseCreate] = Field(min_length=1, max_length=5000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class EvaluationDatasetResponse(BaseModel):
    id: str
    object: str = "vector_store.evaluation_dataset"
    vector_store_id: str
    name: str
    version: int
    status: str
    case_count: int
    created_at: int


class SemanticCoverageConfig(BaseModel):
    k_values: list[int] = Field(default_factory=lambda: [5, 10])
    include_paraphrases: bool = True
    include_language_slices: bool = True

    @field_validator("k_values")
    @classmethod
    def validate_k_values(cls, values: list[int]) -> list[int]:
        normalized = sorted(set(values) | {5, 10})
        if any(value < 1 or value > 100 for value in normalized):
            raise ValueError("k_values entries must be between 1 and 100")
        return normalized


class EvaluationRunCreate(BaseModel):
    type: Literal["semantic_coverage"]
    dataset_id: str
    config: SemanticCoverageConfig = Field(default_factory=SemanticCoverageConfig)


class EvaluationRunResponse(BaseModel):
    id: str
    object: str = "vector_store.evaluation"
    vector_store_id: str
    dataset_id: str
    type: str
    status: str
    config: dict[str, Any]
    summary: dict[str, Any] | None = None
    evaluator_version: str
    error: str | None = None
    created_at: int
    started_at: int | None = None
    completed_at: int | None = None


class EvaluationResultItem(BaseModel):
    id: int
    object: str = "vector_store.evaluation_result"
    case_id: str
    metric: str
    score: float
    severity: str
    details: dict[str, Any]
    created_at: int


class EvaluationResultList(BaseModel):
    object: str = "list"
    data: list[EvaluationResultItem]
    first_id: int | None
    last_id: int | None
    has_more: bool
