import os
import secrets
from pathlib import Path
from datetime import datetime, timedelta

STORAGE_PATH = Path("storage/files")
STORAGE_PATH.mkdir(parents=True, exist_ok=True)


ALLOWED_EXTENSIONS = {
    "pdf",
    "txt",
    "md",
    "json",
    "jsonl",
    "csv",
    "html",
    "docx"
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

    file_path = STORAGE_PATH / file_id

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    metadata = {
        "id": file_id,
        "filename": filename,
        "bytes": len(file_bytes),
        "created_at": int(datetime.utcnow().timestamp()),
        "expires_at": int((datetime.utcnow() + timedelta(seconds=expires_seconds)).timestamp())
    }

    return metadata


async def save_file_stream(upload_file, expires_seconds=2592000):

    validate_extension(upload_file.filename)

    file_id = generate_file_id()
    file_path = STORAGE_PATH / file_id

    size = 0

    with open(file_path, "wb") as f:

        while chunk := await upload_file.read(1024 * 1024):  # 1MB
            size += len(chunk)

            f.write(chunk)

    metadata = {
        "id": file_id,
        "filename": upload_file.filename,
        "bytes": size,
        "path": str(file_path),
        "created_at": int(datetime.utcnow().timestamp()),
        "expires_at": int((datetime.utcnow() + timedelta(seconds=expires_seconds)).timestamp())
    }

    return metadata
