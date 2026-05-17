from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VectorStoreCreate(BaseModel):
    name: Optional[str] = None


class VectorStoreResponse(BaseModel):
    id: str
    object: str = "vector_store"
    name: Optional[str]
    created_at: int
