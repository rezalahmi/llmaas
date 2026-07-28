import json
from typing import Any


async def replace_chunk_inventory(
    pg,
    *,
    api_key_id: int,
    vector_store_id: str,
    file_id: str,
    chunks: list[dict[str, Any]],
):
    chunk_refs = [chunk["chunk_ref"] for chunk in chunks]
    async with pg.transaction():
        await pg.execute(
            """
            DELETE FROM vector_store_chunks
            WHERE api_key_id = $1
              AND vector_store_id = $2
              AND file_id = $3
              AND (
                  chunk_ref IS NULL
                  OR NOT (chunk_ref = ANY($4::text[]))
              )
            """,
            api_key_id,
            vector_store_id,
            file_id,
            chunk_refs,
        )
        if not chunks:
            return
        await pg.executemany(
            """
            INSERT INTO vector_store_chunks (
                vector_store_id,
                id,
                chunk_ref,
                api_key_id,
                file_id,
                chunk_index,
                chunking_strategy,
                chunking_version,
                embedding_model,
                embedding_version,
                reranker_model,
                reranker_version,
                generation_model,
                generation_version,
                vector_index_provider,
                vector_index_version,
                character_count,
                token_count,
                exact_hash,
                identity_status,
                metadata
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                $13, $14, $15, $16, $17, $18, $19, 'registered', $20::jsonb
            )
            ON CONFLICT (api_key_id, vector_store_id, chunk_ref)
            DO UPDATE SET
                id = EXCLUDED.id,
                vector_store_id = EXCLUDED.vector_store_id,
                file_id = EXCLUDED.file_id,
                chunk_index = EXCLUDED.chunk_index,
                chunking_strategy = EXCLUDED.chunking_strategy,
                chunking_version = EXCLUDED.chunking_version,
                embedding_model = EXCLUDED.embedding_model,
                embedding_version = EXCLUDED.embedding_version,
                reranker_model = EXCLUDED.reranker_model,
                reranker_version = EXCLUDED.reranker_version,
                generation_model = EXCLUDED.generation_model,
                generation_version = EXCLUDED.generation_version,
                vector_index_provider = EXCLUDED.vector_index_provider,
                vector_index_version = EXCLUDED.vector_index_version,
                character_count = EXCLUDED.character_count,
                token_count = EXCLUDED.token_count,
                exact_hash = EXCLUDED.exact_hash,
                metadata = EXCLUDED.metadata,
                identity_status = 'registered',
                updated_at = NOW()
            """,
            [
                (
                    vector_store_id,
                    chunk["id"],
                    chunk["chunk_ref"],
                    api_key_id,
                    file_id,
                    chunk["chunk_index"],
                    chunk["chunking_strategy"],
                    chunk["chunking_version"],
                    chunk["embedding_model"],
                    chunk["embedding_version"],
                    chunk["reranker_model"],
                    chunk["reranker_version"],
                    chunk["generation_model"],
                    chunk["generation_version"],
                    chunk["vector_index_provider"],
                    chunk["vector_index_version"],
                    chunk["character_count"],
                    chunk.get("token_count"),
                    chunk["exact_hash"],
                    json.dumps(chunk.get("metadata") or {}, default=str),
                )
                for chunk in chunks
            ],
        )


async def delete_chunk_inventory(
    pg,
    *,
    api_key_id: int,
    vector_store_id: str,
    file_id: str,
):
    return await pg.execute(
        """
        DELETE FROM vector_store_chunks
        WHERE api_key_id = $1 AND vector_store_id = $2 AND file_id = $3
        """,
        api_key_id,
        vector_store_id,
        file_id,
    )


async def resolve_chunk_ref(pg, *, api_key_id: int, chunk_ref: str):
    """Resolve a chunk only inside its owning tenant."""
    return await pg.fetchrow(
        """
        SELECT
            chunk_ref,
            vector_store_id,
            file_id,
            chunk_index,
            chunking_strategy,
            chunking_version,
            embedding_model,
            embedding_version,
            reranker_model,
            reranker_version,
            generation_model,
            generation_version,
            vector_index_provider,
            vector_index_version,
            exact_hash,
            metadata
        FROM vector_store_chunks
        WHERE api_key_id = $1
          AND chunk_ref = $2
          AND identity_status = 'registered'
        """,
        api_key_id,
        chunk_ref,
    )


async def get_chunk_registry_coverage(pg, *, api_key_id: int | None = None):
    """Return attachment-aware coverage without exposing chunk content."""
    return await pg.fetchrow(
        """
        WITH attachment_inventory AS (
            SELECT
                vsf.id,
                vsf.chunk_size,
                vsf.chunk_overlap,
                COUNT(vsc.id) AS chunk_count,
                COUNT(vsc.id) FILTER (
                    WHERE vsc.identity_status = 'registered'
                      AND vsc.chunk_ref IS NOT NULL
                ) AS registered_count,
                COUNT(vsc.id) FILTER (
                    WHERE vsc.identity_status <> 'registered'
                       OR vsc.chunk_ref IS NULL
                ) AS unresolved_count,
                COUNT(vsc.id) FILTER (
                    WHERE vsc.identity_status = 'registered'
                      AND vsc.chunk_ref IS NOT NULL
                      AND NULLIF(vsc.embedding_model, '') IS NOT NULL
                      AND LOWER(vsc.embedding_model) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.embedding_version, '') IS NOT NULL
                      AND LOWER(vsc.embedding_version) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.chunking_strategy, '') IS NOT NULL
                      AND LOWER(vsc.chunking_strategy) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.chunking_version, '') IS NOT NULL
                      AND LOWER(vsc.chunking_version) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.reranker_model, '') IS NOT NULL
                      AND LOWER(vsc.reranker_model) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.reranker_version, '') IS NOT NULL
                      AND LOWER(vsc.reranker_version) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.generation_model, '') IS NOT NULL
                      AND LOWER(vsc.generation_model) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.generation_version, '') IS NOT NULL
                      AND LOWER(vsc.generation_version) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.vector_index_provider, '') IS NOT NULL
                      AND LOWER(vsc.vector_index_provider) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.vector_index_version, '') IS NOT NULL
                      AND LOWER(vsc.vector_index_version) NOT IN ('unknown', 'unversioned')
                ) AS fully_versioned_count
            FROM vector_store_files AS vsf
            JOIN vector_stores AS vs
              ON vs.id = vsf.vector_store_id
            JOIN files AS f
              ON f.id = vsf.file_id
            LEFT JOIN vector_store_chunks AS vsc
              ON vsc.api_key_id = vsf.api_key_id
             AND vsc.vector_store_id = vsf.vector_store_id
             AND vsc.file_id = vsf.file_id
            WHERE vsf.deleted_at IS NULL
              AND vs.deleted_at IS NULL
              AND f.deleted_at IS NULL
              AND vs.status = 'ready'
              AND f.status = 'ready'
              AND vsf.status IN ('ready', 'attached', 'failed')
              AND (f.expires_at IS NULL OR f.expires_at > NOW())
              AND vsf.api_key_id IS NOT NULL
              AND vs.api_key_id = vsf.api_key_id
              AND f.api_key_id = vsf.api_key_id
              AND ($1::bigint IS NULL OR vsf.api_key_id = $1)
            GROUP BY vsf.id, vsf.chunk_size, vsf.chunk_overlap
        )
        SELECT
            COUNT(*) AS total_attachments,
            COUNT(*) FILTER (
                WHERE chunk_count > 0
                  AND registered_count = chunk_count
                  AND fully_versioned_count = chunk_count
            ) AS complete_attachments,
            COUNT(*) FILTER (
                WHERE chunk_count = 0
            ) AS missing_registry_attachments,
            COUNT(*) FILTER (
                WHERE unresolved_count > 0
            ) AS legacy_unresolved_attachments,
            COUNT(*) FILTER (
                WHERE chunk_count > 0
                  AND fully_versioned_count < chunk_count
            ) AS incomplete_version_attachments,
            COUNT(*) FILTER (
                WHERE (chunk_size IS NULL OR chunk_overlap IS NULL)
                  AND NOT (
                      chunk_count > 0
                      AND registered_count = chunk_count
                      AND fully_versioned_count = chunk_count
                  )
            ) AS settings_unknown_attachments,
            COALESCE(SUM(chunk_count), 0) AS total_chunks,
            COALESCE(SUM(registered_count), 0) AS registered_chunks,
            COALESCE(SUM(unresolved_count), 0) AS unresolved_chunks,
            COALESCE(SUM(fully_versioned_count), 0) AS fully_versioned_chunks
        FROM attachment_inventory
        """,
        api_key_id,
    )


async def list_chunk_registry_backfill_candidates(
    pg,
    *,
    api_key_id: int | None = None,
    after_id: str | None = None,
    limit: int = 100,
):
    """List incomplete active attachments using stable keyset pagination."""
    return await pg.fetch(
        """
        WITH candidates AS (
            SELECT
                vsf.id AS attachment_id,
                vsf.vector_store_id,
                vsf.file_id,
                vsf.api_key_id,
                vsf.external_user_id,
                vsf.chunk_size,
                vsf.chunk_overlap,
                f.storage_path,
                f.filename,
                f.ext,
                f.status AS file_status,
                COUNT(vsc.id) AS chunk_count,
                COUNT(vsc.id) FILTER (
                    WHERE vsc.identity_status = 'registered'
                      AND vsc.chunk_ref IS NOT NULL
                ) AS registered_count,
                COUNT(vsc.id) FILTER (
                    WHERE vsc.identity_status = 'registered'
                      AND vsc.chunk_ref IS NOT NULL
                      AND NULLIF(vsc.embedding_model, '') IS NOT NULL
                      AND LOWER(vsc.embedding_model) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.embedding_version, '') IS NOT NULL
                      AND LOWER(vsc.embedding_version) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.chunking_strategy, '') IS NOT NULL
                      AND LOWER(vsc.chunking_strategy) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.chunking_version, '') IS NOT NULL
                      AND LOWER(vsc.chunking_version) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.reranker_model, '') IS NOT NULL
                      AND LOWER(vsc.reranker_model) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.reranker_version, '') IS NOT NULL
                      AND LOWER(vsc.reranker_version) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.generation_model, '') IS NOT NULL
                      AND LOWER(vsc.generation_model) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.generation_version, '') IS NOT NULL
                      AND LOWER(vsc.generation_version) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.vector_index_provider, '') IS NOT NULL
                      AND LOWER(vsc.vector_index_provider) NOT IN ('unknown', 'unversioned')
                      AND NULLIF(vsc.vector_index_version, '') IS NOT NULL
                      AND LOWER(vsc.vector_index_version) NOT IN ('unknown', 'unversioned')
                ) AS fully_versioned_count
            FROM vector_store_files AS vsf
            JOIN vector_stores AS vs
              ON vs.id = vsf.vector_store_id
             AND vs.api_key_id = vsf.api_key_id
            JOIN files AS f
              ON f.id = vsf.file_id
             AND f.api_key_id = vsf.api_key_id
            LEFT JOIN vector_store_chunks AS vsc
              ON vsc.api_key_id = vsf.api_key_id
             AND vsc.vector_store_id = vsf.vector_store_id
             AND vsc.file_id = vsf.file_id
            WHERE vsf.deleted_at IS NULL
              AND vs.deleted_at IS NULL
              AND f.deleted_at IS NULL
              AND vs.status = 'ready'
              AND f.status = 'ready'
              AND vsf.status IN ('ready', 'attached', 'failed')
              AND (f.expires_at IS NULL OR f.expires_at > NOW())
              AND vsf.api_key_id IS NOT NULL
              AND ($1::bigint IS NULL OR vsf.api_key_id = $1)
              AND ($2::text IS NULL OR vsf.id > $2)
            GROUP BY
                vsf.id,
                vsf.vector_store_id,
                vsf.file_id,
                vsf.api_key_id,
                vsf.external_user_id,
                vsf.chunk_size,
                vsf.chunk_overlap,
                f.storage_path,
                f.filename,
                f.ext,
                f.status
        )
        SELECT *
        FROM candidates
        WHERE chunk_count = 0
           OR registered_count < chunk_count
           OR fully_versioned_count < chunk_count
        ORDER BY attachment_id
        LIMIT $3
        """,
        api_key_id,
        after_id,
        limit,
    )


async def mark_chunk_registry_backfill(
    pg,
    *,
    attachment_id: str,
    api_key_id: int,
    status: str,
    error: str | None = None,
):
    return await pg.execute(
        """
        UPDATE vector_store_files
        SET registry_backfill_status = $3,
            registry_backfill_error = $4,
            registry_backfill_attempted_at = NOW(),
            registry_backfilled_at = CASE
                WHEN $3 = 'completed' THEN NOW()
                ELSE registry_backfilled_at
            END,
            updated_at = NOW()
        WHERE id = $1
          AND api_key_id = $2
          AND deleted_at IS NULL
        """,
        attachment_id,
        api_key_id,
        status,
        error,
    )
