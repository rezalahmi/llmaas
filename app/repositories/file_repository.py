# app/repositories/file_repository.py

async def get_file_by_id(pg, file_id: str, external_user_id: str):
    query = """
        SELECT id, filename, bytes, created_at
        FROM files
        WHERE id = $1 AND external_user_id = $2
        LIMIT 1
    """
    return await pg.fetchrow(query, file_id, external_user_id)


async def get_file_for_download(
    pg,
    file_id: str,
    external_user_id: int,
):
    query = """
        SELECT
            id,
            filename,
            bytes,
            content_type,
            storage_backend,
            storage_path,
            storage_key,
            status,
            deleted_at,
            expires_at
        FROM files
        WHERE id = $1
          AND external_user_id = $2
          AND deleted_at IS NULL
        LIMIT 1
    """
    return await pg.fetchrow(query, file_id, external_user_id)
