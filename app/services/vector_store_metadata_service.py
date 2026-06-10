import secrets
import uuid
from typing import Optional
from fastapi import HTTPException


def generate_vector_store_id() -> str:
    return f"vs_{secrets.token_urlsafe(16)}"


def generate_vector_store_file_id(vector_store_id: str, file_id: str) -> str:
    return f"vsfile_{vector_store_id}_{file_id}"


async def create_vector_store_record(
    pg,
    *,
    vector_store_id: str,
    external_user_id: Optional[int],
    api_key_id: Optional[int],
    name: Optional[str],
    collection_name: str,
):
    return await pg.fetchrow(
        """
        INSERT INTO vector_stores (
            id,
            external_user_id,
            api_key_id,
            name,
            collection_name,
            storage_backend,
            status
        )
        VALUES ($1, $2, $3, $4, $5, 'chroma', 'ready')
        RETURNING
            id,
            external_user_id,
            api_key_id,
            name,
            collection_name,
            storage_backend,
            status,
            EXTRACT(EPOCH FROM created_at)::bigint AS created_at
        """,
        vector_store_id,
        external_user_id,
        api_key_id,
        name,
        collection_name,
    )


async def mark_vector_store_failed(pg, *, vector_store_id: str, error: str):
    return await pg.execute(
        """
        UPDATE vector_stores
        SET status = 'failed',
            error = $2,
            updated_at = now()
        WHERE id = $1
        """,
        vector_store_id,
        error,
    )


async def count_user_vector_stores(pg, *, api_key_id: Optional[int]):
    return await pg.fetchval(
        """
        SELECT COUNT(*)
        FROM vector_stores
        WHERE api_key_id = $1
          AND deleted_at IS NULL
          AND status != 'deleted'
        """,
        api_key_id,
    )


async def list_vector_stores_by_api_key(pg, *, api_key_id: Optional[int]):
    return await pg.fetch(
        """
        SELECT
            id,
            name,
            EXTRACT(EPOCH FROM created_at)::bigint AS created_at
        FROM vector_stores
        WHERE api_key_id = $1
          AND deleted_at IS NULL
          AND status != 'deleted'
        ORDER BY created_at DESC
        """,
        api_key_id,
    )


async def get_vector_store_for_owner(
    pg,
    *,
    vector_store_id: str,
    api_key_id: Optional[int],
):
    return await pg.fetchrow(
        """
        SELECT
            id,
            external_user_id,
            api_key_id,
            name,
            collection_name,
            status,
            EXTRACT(EPOCH FROM created_at)::bigint AS created_at
        FROM vector_stores
        WHERE id = $1
          AND api_key_id = $2
          AND deleted_at IS NULL
          AND status != 'deleted'
        """,
        vector_store_id,
        api_key_id,
    )


async def soft_delete_vector_store(
    pg,
    *,
    vector_store_id: str,
    api_key_id: Optional[int],
):
    return await pg.fetchrow(
        """
        UPDATE vector_stores
        SET status = 'deleted',
            deleted_at = now(),
            updated_at = now()
        WHERE id = $1
          AND api_key_id = $2
          AND deleted_at IS NULL
        RETURNING id
        """,
        vector_store_id,
        api_key_id,
    )


async def attach_file_to_vector_store(
    pg,
    *,
    vector_store_id: str,
    file_id: str,
    external_user_id: Optional[int],
    api_key_id: Optional[int],
    status: str = "attached",
):
    vector_store_file_id = generate_vector_store_file_id(vector_store_id, file_id)

    return await pg.fetchrow(
        """
        INSERT INTO vector_store_files (
            id,
            vector_store_id,
            file_id,
            external_user_id,
            api_key_id,
            status
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (id) DO UPDATE
        SET deleted_at = NULL,
            status = EXCLUDED.status,
            error = NULL,
            updated_at = now()
        RETURNING
            id,
            vector_store_id,
            file_id,
            status,
            EXTRACT(EPOCH FROM created_at)::bigint AS created_at
        """,
        vector_store_file_id,
        vector_store_id,
        file_id,
        external_user_id,
        api_key_id,
        status,
    )


async def list_vector_store_files_by_owner(
    pg,
    *,
    vector_store_id: str,
    api_key_id: Optional[int],
):
    return await pg.fetch(
        """
        SELECT
            vsf.id,
            vsf.file_id,
            vsf.vector_store_id,
            vsf.status,
            EXTRACT(EPOCH FROM vsf.created_at)::bigint AS created_at
        FROM vector_store_files vsf
        JOIN vector_stores vs
          ON vs.id = vsf.vector_store_id
        WHERE vsf.vector_store_id = $1
          AND vs.api_key_id = $2
          AND vs.deleted_at IS NULL
          AND vsf.deleted_at IS NULL
          AND vsf.status != 'deleted'
        ORDER BY vsf.created_at ASC
        """,
        vector_store_id,
        api_key_id,
    )


async def soft_delete_vector_store_files(pg, *, vector_store_id: str):
    return await pg.execute(
        """
        UPDATE vector_store_files
        SET status = 'deleted',
            deleted_at = now(),
            updated_at = now()
        WHERE vector_store_id = $1
          AND deleted_at IS NULL
        """,
        vector_store_id,
    )


async def upsert_vector_store_file(
    pg, 
    vector_store_id: str, 
    file_id: str, 
    external_user_id: int, 
    api_key_id: int, 
    status: str,
    batch_id: str = None,
    error: str = None
):
    """
    ثبت یا به‌روزرسانی وضعیت فایل در یک وکتور استور.
    اگر فایل قبلاً اتچ شده باشد، وضعیت آن آپدیت می‌شود (مثلاً از processing به ready).
    """
    # ساخت آی‌دی جدید فقط برای رکوردهای جدید
    new_id = f"vsf_{uuid.uuid4().hex[:20]}"
    
    query = """
        INSERT INTO vector_store_files (
            id, vector_store_id, file_id, external_user_id, api_key_id, status, batch_id, error, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        ON CONFLICT (vector_store_id, file_id) WHERE deleted_at IS NULL
        DO UPDATE SET 
            status = EXCLUDED.status,
            batch_id = COALESCE(EXCLUDED.batch_id, vector_store_files.batch_id),
            error = EXCLUDED.error,
            updated_at = NOW()
        RETURNING id, created_at;
    """
    return await pg.fetchrow(
        query, 
        new_id, vector_store_id, file_id, external_user_id, api_key_id, status, batch_id, error
    )


async def get_vector_store_files_list(pg, vector_store_id: str, limit: int = 20, after: str = None):
    # کوئری برای گرفتن لیست فایل‌ها به همراه اطلاعات تکمیلی
    query = """
        SELECT 
            vsf.file_id, 
            vsf.status, 
            vsf.error as last_error, 
            vsf.created_at, 
            vsf.vector_store_id,
            f.size as usage_bytes
        FROM vector_store_files vsf
        LEFT JOIN files f ON vsf.file_id = f.id
        WHERE vsf.vector_store_id = $1 AND vsf.deleted_at IS NULL
    """
    params = [vector_store_id]
    
    if after:
        query += " AND vsf.file_id > $2"
        params.append(after)
        
    query += " ORDER BY vsf.file_id ASC LIMIT $3"
    params.append(limit)
    
    return await pg.fetch(query, *params)
