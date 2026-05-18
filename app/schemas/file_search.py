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
    text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FileSearchResponse(BaseModel):
    results: List[FileSearchResultChunk]
