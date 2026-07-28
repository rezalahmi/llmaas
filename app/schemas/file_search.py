# app/schemas/file_search.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class FileSearchQuery(BaseModel):
    vector_store_ids: List[str]
    query: str
    max_results: int = 5
    filters: Optional[Dict[str, Any]] = None


class FileSearchResultChunk(BaseModel):
    file_id: str
    vector_store_id: str
    document_id: str
    chunk_ref: str = Field(exclude=True)
    text: str
    score: float
    dense_score: float | None = Field(default=None, exclude=True)
    rerank_score: float | None = Field(default=None, exclude=True)
    dense_rank: int | None = Field(default=None, exclude=True)
    rerank_rank: int | None = Field(default=None, exclude=True)
    dense_distance: float | None = Field(default=None, exclude=True)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalCandidateFact(BaseModel):
    source_id: str
    chunk_ref: str
    vector_store_id: str
    dense_distance: float
    dense_rank: int
    dense_relevance_score: None = None
    rerank_score: float | None = None
    rerank_rank: int | None = None
    candidate: bool = True
    selected: bool


class FileSearchResponse(BaseModel):
    results: List[FileSearchResultChunk]
    retrieval_facts: List[RetrievalCandidateFact] = Field(
        default_factory=list,
        exclude=True,
    )
    retrieval_runtime: Dict[str, Any] = Field(default_factory=dict, exclude=True)
