from pathlib import Path
import hashlib
import os
import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.repositories.file_repository import get_file_by_id, get_file_for_download
from fastapi.responses import FileResponse



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




async def get_file_content(
    pg,
    *,
    file_id: str,
    external_user_id: int,
):
    row = await get_file_for_download(
        pg,
        file_id=file_id,
        external_user_id=external_user_id,
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found."
        )

    # ✅ وضعیت فایل
    if row["status"] != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File is not ready for download (status={row['status']})."
        )

    # ✅ بررسی expiration
    if row["expires_at"]:
        from datetime import datetime, timezone
        if row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="File has expired."
            )

    backend = row["storage_backend"]

    # =======================
    # DISK STORAGE
    # =======================
    if backend == "disk":
        file_path = row["storage_path"]

        if not file_path or not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File content not found on disk."
            )

        return FileResponse(
            path=file_path,
            filename=row["filename"],
            media_type=row["content_type"] or "application/octet-stream",
        )

    # =======================
    # S3 STORAGE (برای آینده)
    # =======================
    elif backend == "s3":
        # اینجا بعداً می‌تونی presigned URL بسازی
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="S3 backend not implemented yet."
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unknown storage backend."
        )


#TODO expiration → soft delete → purge