from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class VectorStoreCreate(BaseModel):
    name: Optional[str] = None


class VectorStoreResponse(BaseModel):
    id: str
    object: str = "vector_store"
    name: Optional[str]
    created_at: int


class VectorStoreDeletedResponse(BaseModel):
    id: str
    object: str
    deleted: bool


class VectorStoreFileItem(BaseModel):
    id: str
    object: str = "vector_store.file"
    created_at: int
    vector_store_id: str

class VectorStoreFileListResponse(BaseModel):
    object: str = "list"
    data: List[VectorStoreFileItem]
    first_id: Optional[str]
    last_id: Optional[str]
    has_more: bool

class VectorStorePatchRequest(BaseModel):
    name: str | None = Field(None, max_length=255)

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v):
        if v is not None and not v.strip():
            raise ValueError('name cannot be empty or just whitespace')
        return v.strip() if v else v