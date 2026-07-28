BEGIN;

ALTER TABLE vector_store_files
    ADD COLUMN IF NOT EXISTS chunk_size INTEGER,
    ADD COLUMN IF NOT EXISTS chunk_overlap INTEGER,
    ADD COLUMN IF NOT EXISTS registry_backfill_status TEXT,
    ADD COLUMN IF NOT EXISTS registry_backfill_error TEXT,
    ADD COLUMN IF NOT EXISTS registry_backfill_attempted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS registry_backfilled_at TIMESTAMPTZ;

UPDATE vector_store_files AS vsf
SET api_key_id = COALESCE(vsf.api_key_id, vs.api_key_id, f.api_key_id),
    external_user_id = COALESCE(
        vsf.external_user_id,
        vs.external_user_id,
        f.external_user_id
    )
FROM vector_stores AS vs, files AS f
WHERE vs.id = vsf.vector_store_id
  AND f.id = vsf.file_id
  AND (vsf.api_key_id IS NULL OR vsf.external_user_id IS NULL);

ALTER TABLE vector_store_files
    DROP CONSTRAINT IF EXISTS vector_store_files_chunking_config_check,
    DROP CONSTRAINT IF EXISTS vector_store_files_registry_backfill_status_check;

ALTER TABLE vector_store_files
    ADD CONSTRAINT vector_store_files_chunking_config_check
    CHECK (
        (chunk_size IS NULL AND chunk_overlap IS NULL)
        OR (
            chunk_size > 0
            AND chunk_overlap >= 0
            AND chunk_overlap < chunk_size
        )
    ),
    ADD CONSTRAINT vector_store_files_registry_backfill_status_check
    CHECK (
        registry_backfill_status IS NULL
        OR registry_backfill_status IN (
            'running',
            'completed',
            'failed',
            'settings_unknown'
        )
    );

CREATE INDEX IF NOT EXISTS idx_vector_store_files_registry_backfill
ON vector_store_files(registry_backfill_status, id)
WHERE deleted_at IS NULL;

COMMENT ON COLUMN vector_store_files.registry_backfill_status IS
'Operational P1.5 backfill state; registry truth is still derived from chunk rows.';

COMMIT;
