from pathlib import Path
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.repositories.file_repository import get_file_by_id

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_PATH = BASE_DIR / "storage" / "files"
STORAGE_PATH.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {
    "pdf",
    "txt",
    "md",
    "json",
    "jsonl",
    "csv",
    "html",
    "docx",
    "xlsx",
    "xls",
    "pptx"
}


def generate_file_id():
    return f"file_{secrets.token_urlsafe(16)}"

def validate_extension(filename: str):
    ext = filename.split(".")[-1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    return ext


def save_file(file_bytes: bytes, filename: str, expires_seconds: int = 2592000):
    file_id = generate_file_id()

    
    ext = os.path.splitext(filename)[1].lower()

    os.makedirs(STORAGE_PATH, exist_ok=True)

    file_path = STORAGE_PATH / f"{file_id}{ext}"


    with open(file_path, "wb") as f:
        f.write(file_bytes)

    metadata = {
        "id": file_id,
        "filename": filename,
        "path": str(file_path),
        "bytes": len(file_bytes),
        "created_at": int(datetime.utcnow().timestamp()),
        "expires_at": int((datetime.utcnow() + timedelta(seconds=expires_seconds)).timestamp())
    }

    return metadata


async def save_file_stream(upload_file, file_id: str, expires_seconds=2592000):
    ext = validate_extension(upload_file.filename)

    suffix = os.path.splitext(upload_file.filename)[1].lower()
    os.makedirs(STORAGE_PATH, exist_ok=True)

    file_path = os.path.join(STORAGE_PATH, f"{file_id}{suffix}")
    storage_key = f"files/{file_id}{suffix}"

    size = 0
    sha256 = hashlib.sha256()

    with open(file_path, "wb") as f:
        while chunk := await upload_file.read(1024 * 1024):  # 1MB
            size += len(chunk)
            sha256.update(chunk)
            f.write(chunk)

    metadata = {
        "id": file_id,
        "filename": upload_file.filename,
        "ext": ext,
        "bytes": size,
        "path": str(file_path),
        "storage_key": storage_key,
        "sha256": sha256.hexdigest(),
        "created_at": int(datetime.utcnow().timestamp()),
        "expires_at": int((datetime.utcnow() + timedelta(seconds=expires_seconds)).timestamp())
    }

    return metadata

async def retrieve_user_file(pg, file_id: str, external_user_id: str):
    row = await get_file_by_id(pg, file_id, external_user_id)

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found."
        )

    return {
        "id": row["id"],
        "object": "file",
        "filename": row["filename"],
        "bytes": row["bytes"],
        "created_at": int(row["created_at"].timestamp()) if row["created_at"] else None,
    }