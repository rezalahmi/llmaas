async def get_vector_store_by_id(pg, *, vector_store_id: str, api_key_id: int):
    return await pg.fetchrow(
        """
        SELECT
            vs.id,
            vs.name,
            vs.status,
            vs.error,
            vs.created_at,
            vs.updated_at,
            vs.storage_backend,
            vs.collection_name,

            COALESCE(SUM(
                CASE
                    WHEN vsf.deleted_at IS NULL THEN COALESCE(f.bytes, 0)
                    ELSE 0
                END
            ), 0) AS usage_bytes,

            COUNT(*) FILTER (
                WHERE vsf.deleted_at IS NULL
                  AND vsf.status IN ('attached', 'processing')
            ) AS in_progress_count,

            COUNT(*) FILTER (
                WHERE vsf.deleted_at IS NULL
                  AND vsf.status = 'ready'
            ) AS completed_count,

            COUNT(*) FILTER (
                WHERE vsf.deleted_at IS NULL
                  AND vsf.status = 'failed'
            ) AS failed_count,

            COUNT(*) FILTER (
                WHERE vsf.deleted_at IS NULL
            ) AS total_count

        FROM vector_stores vs
        LEFT JOIN vector_store_files vsf
            ON vsf.vector_store_id = vs.id
        LEFT JOIN files f
            ON f.id = vsf.file_id
           AND f.deleted_at IS NULL

        WHERE vs.id = $1
          AND vs.api_key_id = $2
          AND vs.deleted_at IS NULL

        GROUP BY
            vs.id,
            vs.name,
            vs.status,
            vs.error,
            vs.created_at,
            vs.updated_at,
            vs.storage_backend,
            vs.collection_name

        LIMIT 1
        """,
        vector_store_id,
        api_key_id
    )


async def patch_vector_store(pg, *, vector_store_id: str, api_key_id: int, name: str):
    query = """
        UPDATE vector_stores
        SET 
            name = $3,
            updated_at = NOW()
        WHERE id = $1 
          AND api_key_id = $2 
          AND deleted_at IS NULL
        RETURNING id, name, status, created_at
    """
    return await pg.fetchrow(query, vector_store_id, api_key_id, name)

async def get_vector_store_file(
    pg,
    *,
    vector_store_id: str,
    file_id: str,
    api_key_id: int
):
    return await pg.fetchrow(
        """
        SELECT
            vsf.vector_store_id,
            vsf.file_id,
            vsf.status,
            vsf.error,
            vsf.created_at
        FROM vector_store_files vsf
        JOIN files f ON f.id = vsf.file_id
        WHERE vsf.vector_store_id = $1
          AND vsf.file_id = $2
          AND f.api_key_id = $3
          AND vsf.deleted_at IS NULL
        """,
        vector_store_id,
        file_id,
        api_key_id
    )
