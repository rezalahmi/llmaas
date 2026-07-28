from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime


class VectorStoreFileCreate(BaseModel):
    file_id: str
    chunk_size: int = Field(default=800, ge=1)
    chunk_overlap: int = Field(default=200, ge=0)

    @model_validator(mode="after")
    def overlap_is_smaller_than_size(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class VectorStoreFileResponse(BaseModel):
    id: str
    object: str = "vector_store.file"
    created_at: int
    vector_store_id: str
    status: str
    last_error: Optional[str] = None


class VectorStoreFileDetachRequest(BaseModel):
    delete_file: Optional[bool] = False


class VectorStoreFileDetachResponse(BaseModel):
    id: str
    vector_store_id: str
    file_id: str
    status: str
