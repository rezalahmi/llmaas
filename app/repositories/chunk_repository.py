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
    async with pg.transaction():
        await pg.execute(
            """
            DELETE FROM vector_store_chunks
            WHERE vector_store_id = $1 AND file_id = $2
            """,
            vector_store_id,
            file_id,
        )
        if not chunks:
            return
        await pg.executemany(
            """
            INSERT INTO vector_store_chunks (
                vector_store_id,
                id,
                api_key_id,
                file_id,
                chunk_index,
                chunking_strategy,
                chunking_version,
                embedding_version,
                character_count,
                token_count,
                exact_hash,
                metadata
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb
            )
            """,
            [
                (
                    vector_store_id,
                    chunk["id"],
                    api_key_id,
                    file_id,
                    chunk["chunk_index"],
                    chunk["chunking_strategy"],
                    chunk["chunking_version"],
                    chunk.get("embedding_version"),
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
    vector_store_id: str,
    file_id: str,
):
    return await pg.execute(
        """
        DELETE FROM vector_store_chunks
        WHERE vector_store_id = $1 AND file_id = $2
        """,
        vector_store_id,
        file_id,
    )
