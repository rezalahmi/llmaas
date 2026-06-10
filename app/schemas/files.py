from pydantic import BaseModel
from typing import Optional, List


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    bytes: int


class FileListResponse(BaseModel):
    files: List[FileUploadResponse]


class FileResponse(BaseModel):
    id: str
    object: str = "file"
    filename: str
    bytes: int
    created_at: int | None
