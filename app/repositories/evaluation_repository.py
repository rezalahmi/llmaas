import json
import secrets
from typing import Any


def generate_dataset_id() -> str:
    return f"evalds_{secrets.token_urlsafe(16)}"


def generate_case_id() -> str:
    return f"evalcase_{secrets.token_urlsafe(16)}"


def generate_run_id() -> str:
    return f"vseval_{secrets.token_urlsafe(16)}"


async def create_dataset(
    pg,
    *,
    dataset_id: str,
    api_key_id: int,
    vector_store_id: str,
    name: str,
    version: int,
    cases: list[dict[str, Any]],
):
    async with pg.transaction():
        dataset = await pg.fetchrow(
            """
            INSERT INTO evaluation_datasets (
                id, api_key_id, vector_store_id, name, version
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, vector_store_id, name, version, status, created_at
            """,
            dataset_id,
            api_key_id,
            vector_store_id,
            name,
            version,
        )

        rows = [
            (
                generate_case_id(),
                dataset_id,
                case["query"],
                case["gold_chunk_ids"],
                case["paraphrases"],
                case.get("language"),
                case.get("intent"),
                case.get("rarity"),
                json.dumps(case.get("metadata") or {}),
            )
            for case in cases
        ]
        await pg.executemany(
            """
            INSERT INTO evaluation_cases (
                id,
                dataset_id,
                query,
                gold_chunk_ids,
                paraphrases,
                language,
                intent,
                rarity,
                metadata
            )
            VALUES ($1, $2, $3, $4::text[], $5::text[], $6, $7, $8, $9::jsonb)
            """,
            rows,
        )

    return {**dict(dataset), "case_count": len(cases)}


async def get_dataset_for_owner(
    pg,
    *,
    dataset_id: str,
    vector_store_id: str,
    api_key_id: int,
):
    return await pg.fetchrow(
        """
        SELECT
            d.id,
            d.vector_store_id,
            d.name,
            d.version,
            d.status,
            d.created_at,
            COUNT(c.id)::int AS case_count
        FROM evaluation_datasets d
        LEFT JOIN evaluation_cases c ON c.dataset_id = d.id
        WHERE d.id = $1
          AND d.vector_store_id = $2
          AND d.api_key_id = $3
        GROUP BY d.id
        """,
        dataset_id,
        vector_store_id,
        api_key_id,
    )


async def list_dataset_cases(pg, *, dataset_id: str):
    return await pg.fetch(
        """
        SELECT
            id,
            query,
            gold_chunk_ids,
            paraphrases,
            language,
            intent,
            rarity,
            metadata
        FROM evaluation_cases
        WHERE dataset_id = $1
        ORDER BY created_at, id
        """,
        dataset_id,
    )


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


async def create_evaluation_run(
    pg,
    *,
    run_id: str,
    api_key_id: int,
    vector_store_id: str,
    dataset_id: str,
    evaluation_type: str,
    config: dict[str, Any],
    evaluator_version: str,
):
    return await pg.fetchrow(
        """
        INSERT INTO vector_store_evaluation_runs (
            id,
            api_key_id,
            vector_store_id,
            dataset_id,
            type,
            config,
            evaluator_version
        )
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
        RETURNING *
        """,
        run_id,
        api_key_id,
        vector_store_id,
        dataset_id,
        evaluation_type,
        json.dumps(config),
        evaluator_version,
    )


async def get_evaluation_run_for_owner(
    pg,
    *,
    run_id: str,
    vector_store_id: str,
    api_key_id: int,
):
    return await pg.fetchrow(
        """
        SELECT *
        FROM vector_store_evaluation_runs
        WHERE id = $1
          AND vector_store_id = $2
          AND api_key_id = $3
        """,
        run_id,
        vector_store_id,
        api_key_id,
    )


async def get_evaluation_run_for_worker(pg, *, run_id: str):
    return await pg.fetchrow(
        """
        SELECT *
        FROM vector_store_evaluation_runs
        WHERE id = $1
        """,
        run_id,
    )


async def mark_evaluation_running(pg, *, run_id: str):
    return await pg.fetchrow(
        """
        UPDATE vector_store_evaluation_runs
        SET status = 'running',
            started_at = COALESCE(started_at, NOW()),
            completed_at = NULL,
            lease_expires_at = NOW() + INTERVAL '30 minutes',
            error = NULL,
            updated_at = NOW()
        WHERE id = $1
          AND (
              status IN ('queued', 'failed')
              OR (
                  status = 'running'
                  AND lease_expires_at < NOW()
              )
          )
        RETURNING *
        """,
        run_id,
    )


async def renew_evaluation_lease(pg, *, run_id: str):
    return await pg.execute(
        """
        UPDATE vector_store_evaluation_runs
        SET lease_expires_at = NOW() + INTERVAL '30 minutes',
            updated_at = NOW()
        WHERE id = $1
          AND status = 'running'
        """,
        run_id,
    )


async def replace_evaluation_results(
    pg,
    *,
    run_id: str,
    results: list[dict[str, Any]],
):
    async with pg.transaction():
        await pg.execute(
            "DELETE FROM vector_store_evaluation_results WHERE run_id = $1",
            run_id,
        )
        if not results:
            return
        await pg.executemany(
            """
            INSERT INTO vector_store_evaluation_results (
                run_id, case_id, metric, score, severity, details
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            [
                (
                    run_id,
                    result["case_id"],
                    result["metric"],
                    result["score"],
                    result["severity"],
                    json.dumps(result["details"]),
                )
                for result in results
            ],
        )


async def mark_evaluation_completed(
    pg,
    *,
    run_id: str,
    summary: dict[str, Any],
):
    return await pg.fetchrow(
        """
        UPDATE vector_store_evaluation_runs
        SET status = 'completed',
            summary = $2::jsonb,
            completed_at = NOW(),
            lease_expires_at = NULL,
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        """,
        run_id,
        json.dumps(summary),
    )


async def mark_evaluation_failed(pg, *, run_id: str, error: str):
    return await pg.execute(
        """
        UPDATE vector_store_evaluation_runs
        SET status = 'failed',
            error = $2,
            completed_at = NOW(),
            lease_expires_at = NULL,
            updated_at = NOW()
        WHERE id = $1
        """,
        run_id,
        error[:2000],
    )


async def list_evaluation_results(
    pg,
    *,
    run_id: str,
    after: int | None,
    limit: int,
):
    return await pg.fetch(
        """
        SELECT id, case_id, metric, score, severity, details, created_at
        FROM vector_store_evaluation_results
        WHERE run_id = $1
          AND ($2::bigint IS NULL OR id > $2)
        ORDER BY id
        LIMIT $3
        """,
        run_id,
        after,
        limit + 1,
    )
