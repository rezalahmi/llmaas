# P1 Chunk Registry backfill and coverage

## Rule

Legacy chunk identity or dependency versions must not be guessed. Rows created
before migration `009` remain `legacy_unresolved` until their source file is
re-ingested with explicit P1 configuration.

## Rollout

1. Apply `009_versioned_chunk_identity.sql` and
   `010_chunk_registry_backfill.sql`.
2. Set non-placeholder values for:
   `EMBEDDING_MODEL`, `EMBEDDING_MODEL_VERSION`, `RERANKER_MODEL`,
   `RERANKER_MODEL_VERSION`, `CHUNKING_STRATEGY`, `CHUNKING_VERSION`,
   `GENERATION_MODEL`, `GENERATION_MODEL_VERSION`, `VECTOR_INDEX_PROVIDER`,
   and `VECTOR_INDEX_VERSION`.
3. Run the global attachment-aware coverage inventory. It detects ready
   attachments with no registry rows, so an empty registry cannot produce a
   false 100% result. The report contains counts only and never reads content:

   ```text
   python -m scripts.chunk_registry_coverage --fail-under 100
   ```

4. Preview the global maintenance job. This is also the safe default Docker
   command:

   ```text
   docker compose --profile maintenance run --rm chunk_registry_backfill
   ```

5. Process attachments whose original chunk settings are known:

   ```text
   docker compose --profile maintenance run --rm chunk_registry_backfill \
     python -m scripts.backfill_chunk_registry --concurrency 2
   ```

6. Old attachments do not have persisted `chunk_size`/`chunk_overlap`. They are
   reported as `settings_unknown` and are not changed. After explicit approval,
   apply chosen defaults:

   ```text
   docker compose --profile maintenance run --rm chunk_registry_backfill \
     python -m scripts.backfill_chunk_registry \
     --use-default-chunking \
     --default-chunk-size 800 \
     --default-chunk-overlap 400 \
     --concurrency 2
   ```

7. Repeat coverage until attachment and fully-versioned coverage are 100%.
   Production promotion is blocked below 100%.

Useful controls are `--dry-run`, `--api-key-id`, `--limit`, `--page-size`, and
`--concurrency`. The job uses a PostgreSQL advisory lock, isolates failures per
attachment, stores only sanitized failure codes, and is resumable: complete
attachments leave the candidate query while incomplete/failed ones remain
eligible for the next run.

Changing chunking strategy, version, size, or overlap intentionally creates a
new logical identity. Re-ingestion with identical source text and identical
settings produces the same identities. The same logical `chunk_ref` may have
independent placement rows in multiple Vector Stores owned by the same tenant.

## Rollback

Application rollback may continue reading legacy Chroma IDs. Do not drop the
new registry columns or overwrite registered identities. If re-ingestion fails,
the file remains eligible for another controlled re-ingestion and coverage
continues to report it as unresolved.
