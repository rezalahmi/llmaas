from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VectorStoreFileCreate(BaseModel):
    file_id: str
    chunk_size: int = 800
    chunk_overlap: int = 200


class VectorStoreFileResponse(BaseModel):
    id: str
    object: str = "vector_store.file"
    created_at: int
    vector_store_id: str
    status: str
    last_error: Optional[str] = None
