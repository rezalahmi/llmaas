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
    """Return inventory coverage without exposing chunk content."""
    return await pg.fetchrow(
        """
        SELECT
            COUNT(*) AS total_chunks,
            COUNT(*) FILTER (
                WHERE identity_status = 'registered'
                  AND chunk_ref IS NOT NULL
            ) AS registered_chunks,
            COUNT(*) FILTER (
                WHERE identity_status <> 'registered'
                   OR chunk_ref IS NULL
            ) AS unresolved_chunks,
            COUNT(*) FILTER (
                WHERE embedding_model IS NOT NULL
                  AND embedding_version IS NOT NULL
                  AND reranker_model IS NOT NULL
                  AND reranker_version IS NOT NULL
                  AND generation_model IS NOT NULL
                  AND generation_version IS NOT NULL
                  AND vector_index_provider IS NOT NULL
                  AND vector_index_version IS NOT NULL
            ) AS fully_versioned_chunks
        FROM vector_store_chunks
        WHERE ($1::bigint IS NULL OR api_key_id = $1)
        """,
        api_key_id,
    )
