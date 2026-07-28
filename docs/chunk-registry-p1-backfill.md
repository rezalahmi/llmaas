# P1 Chunk Registry backfill and coverage

## Rule

Legacy chunk identity or dependency versions must not be guessed. Rows created
before migration `009` remain `legacy_unresolved` until their source file is
re-ingested with explicit P1 configuration.

## Rollout

1. Apply `009_versioned_chunk_identity.sql`.
2. Set non-placeholder values for:
   `EMBEDDING_MODEL`, `EMBEDDING_MODEL_VERSION`, `RERANKER_MODEL`,
   `RERANKER_MODEL_VERSION`, `CHUNKING_STRATEGY`, `CHUNKING_VERSION`,
   `GENERATION_MODEL`, `GENERATION_MODEL_VERSION`, `VECTOR_INDEX_PROVIDER`,
   and `VECTOR_INDEX_VERSION`.
3. Run the coverage inventory per tenant. The report contains counts only and
   never reads chunk content:

   ```text
   python -m scripts.chunk_registry_coverage --api-key-id 42 --fail-under 100
   ```

4. Re-ingest attached files for tenants with unresolved rows using the original
   approved chunking settings. Re-ingestion writes deterministic `chunk_ref`
   values to Chroma and PostgreSQL atomically at registry level.
5. Repeat the inventory until both registered and fully-versioned coverage are
   100%. Production promotion is blocked below 100%.

Changing chunking strategy, version, size, or overlap intentionally creates a
new logical identity. Re-ingestion with identical source text and identical
settings produces the same identities. The same logical `chunk_ref` may have
independent placement rows in multiple Vector Stores owned by the same tenant.

## Rollback

Application rollback may continue reading legacy Chroma IDs. Do not drop the
new registry columns or overwrite registered identities. If re-ingestion fails,
the file remains eligible for another controlled re-ingestion and coverage
continues to report it as unresolved.
