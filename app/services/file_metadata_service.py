from datetime import datetime, timedelta, timezone
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

async def create_file_uploading(
    pg,
    *,
    file_id: str,
    external_user_id: int | None,
    api_key_id: int | None,
    filename: str,
    content_type: str | None,
    expires_seconds: int = 2592000,
):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_seconds)
    
    await pg.execute(
        """
        insert into files (
            id,
            external_user_id,
            api_key_id,
            filename,
            ext,
            bytes,
            content_type,
            storage_backend,
            storage_key,
            storage_path,
            sha256,
            status,
            error,
            created_at,
            expires_at
        )
        values (
            $1, $2, $3, $4, '',
            0, $5, 'disk', '',
            null, null, 'uploading', null, $6, $7
        )
        """,
        file_id,
        external_user_id,
        api_key_id,
        filename,
        content_type,
        now,
        expires_at,
    )

    return {
        "created_at": now,
        "expires_at": expires_at,
    }


async def mark_file_ready(
    pg,
    *,
    file_id: str,
    ext: str,
    bytes_: int,
    storage_key: str,
    storage_path: str | None,
    sha256: str | None = None,
    storage_backend: str = "disk",
):
    await pg.execute(
        """
        update files
        set
            ext = $2,
            bytes = $3,
            storage_backend = $4,
            storage_key = $5,
            storage_path = $6,
            sha256 = $7,
            status = 'ready',
            error = null
        where id = $1
        """,
        file_id,
        ext,
        bytes_,
        storage_backend,
        storage_key,
        storage_path,
        sha256,
    )


async def mark_file_failed(
    pg,
    *,
    file_id: str,
    error: str,
):
    await pg.execute(
        """
        update files
        set
            status = 'failed',
            error = $2
        where id = $1
        """,
        file_id,
        error[:1000],
    )


async def list_files_by_user(
    pg,
    *,
    external_user_id: int,
):
    rows = await pg.fetch(
        """
        select id, filename, bytes
        from files
        where external_user_id = $1
          AND deleted_at is null
          AND (expires_at IS NULL OR expires_at > NOW())
          AND status = 'ready'
        order by created_at desc
        """,
        external_user_id,
    )

    return [dict(row) for row in rows]


async def delete_file_record(pg, *, file_id: str, api_key_id: str):
    """
    فایل را به صورت منطقی (Soft Delete) حذف می‌کند.
    فقط در صورتی که فایل متعلق به همان API Key باشد.
    """
    return await pg.execute(
        """
        UPDATE files
        SET deleted_at = NOW(),
            status = 'deleted'
        WHERE id = $1 
          AND api_key_id = $2
          AND deleted_at IS NULL
          AND (expires_at IS NULL OR expires_at > NOW())
        """,
        file_id,
        api_key_id
    )


async def get_file_metadata(pg, file_id: str):
    """
    اطلاعات فایل را از جدول files در Postgres بازیابی می‌کند.
    """
    query = """
        SELECT id, storage_path, filename, ext, api_key_id, external_user_id, status 
        FROM files 
        WHERE id = $1
    """
    try:
        record = await pg.fetchrow(query, file_id)
        if not record:
            return None
        
        # تبدیل record به dict برای راحتی کار
        return dict(record)
        
    except Exception as e:
        logger.error(f"Database error while fetching file {file_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error occurred.")