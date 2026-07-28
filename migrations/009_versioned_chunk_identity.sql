BEGIN;

ALTER TABLE vector_store_chunks
    ADD COLUMN IF NOT EXISTS chunk_ref TEXT,
    ADD COLUMN IF NOT EXISTS identity_status TEXT NOT NULL DEFAULT 'legacy_unresolved',
    ADD COLUMN IF NOT EXISTS embedding_model TEXT,
    ADD COLUMN IF NOT EXISTS reranker_model TEXT,
    ADD COLUMN IF NOT EXISTS reranker_version TEXT,
    ADD COLUMN IF NOT EXISTS generation_model TEXT,
    ADD COLUMN IF NOT EXISTS generation_version TEXT,
    ADD COLUMN IF NOT EXISTS vector_index_provider TEXT,
    ADD COLUMN IF NOT EXISTS vector_index_version TEXT;

ALTER TABLE vector_store_chunks
    DROP CONSTRAINT IF EXISTS vector_store_chunks_identity_status_check;

ALTER TABLE vector_store_chunks
    ADD CONSTRAINT vector_store_chunks_identity_status_check
    CHECK (identity_status IN ('registered', 'legacy_unresolved'));

DROP INDEX IF EXISTS uq_vector_store_chunks_tenant_chunk_ref;

CREATE UNIQUE INDEX IF NOT EXISTS uq_vector_store_chunks_tenant_store_chunk_ref
ON vector_store_chunks(api_key_id, vector_store_id, chunk_ref);

CREATE INDEX IF NOT EXISTS idx_vector_store_chunks_registry_coverage
ON vector_store_chunks(api_key_id, identity_status);

CREATE INDEX IF NOT EXISTS idx_vector_store_chunks_chunk_ref
ON vector_store_chunks(chunk_ref);

COMMENT ON COLUMN vector_store_chunks.chunk_ref IS
'Opaque deterministic chunk identity; resolvable only with api_key_id.';

COMMENT ON COLUMN vector_store_chunks.identity_status IS
'registered for P1 identities; legacy_unresolved until controlled re-ingestion.';

COMMIT;
