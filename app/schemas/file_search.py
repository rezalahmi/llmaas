from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class FileSearchQuery(BaseModel):
    vector_store_ids: List[str]
    query: str
    max_results: int = 5
    # بعداً:
    # filters: Optional[Dict[str, Any]] = None
    # include_vectors: bool = False


class FileSearchResultChunk(BaseModel):
    file_id: str
    vector_store_id: str
    document_id: str  # ID ای که هنگام collection.add ثبت کردیم
    text: str
    score: float
    metadata: Dict[str, Any] = {}


class FileSearchResponse(BaseModel):
    results: List[FileSearchResultChunk]
