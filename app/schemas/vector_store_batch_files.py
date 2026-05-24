from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ChunkingConfig(BaseModel):
    chunk_size: int = Field(default=800, ge=100, le=4096)
    chunk_overlap: int = Field(default=400, ge=0)

class VectorStoreFileBatchCreate(BaseModel):
    file_ids: List[str]
    chunking: Optional[ChunkingConfig] = None

class VectorStoreFileBatchFileResult(BaseModel):
    file_id: str
    status: str  # "completed" | "failed"
    error: Optional[str] = None
    # در صورت موفقیت، جزئیات فایلِ اضافه شده برگردد
    result: Optional[Dict[str, Any]] = None 

class VectorStoreFileBatchResponse(BaseModel):
    vector_store_id: str
    status: str = "completed"
    file_results: List[VectorStoreFileBatchFileResult]
