from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any

class ChunkingConfig(BaseModel):
    chunk_size: int = Field(default=800, ge=100, le=4096)
    chunk_overlap: int = Field(default=400, ge=0)

    @model_validator(mode="after")
    def overlap_is_smaller_than_size(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

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
    id: str
    object: str = "vector_store.file_batch"
    vector_store_id: str
    status: str = "completed"
    created_at: int



