BEGIN;

CREATE TABLE IF NOT EXISTS vector_stores (
    id text PRIMARY KEY,

    external_user_id bigint NULL,
    api_key_id bigint NULL REFERENCES api_keys(id) ON DELETE SET NULL,

    name text NULL,

    storage_backend text NOT NULL DEFAULT 'chroma',
    collection_name text NOT NULL UNIQUE,

    status text NOT NULL DEFAULT 'ready',
    error text NULL,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz NULL,

    CONSTRAINT vector_stores_status_check
        CHECK (status IN ('creating', 'ready', 'failed', 'deleted')),

    CONSTRAINT vector_stores_storage_backend_check
        CHECK (storage_backend IN ('chroma'))
);

CREATE TABLE IF NOT EXISTS vector_store_files (
    id text PRIMARY KEY,

    vector_store_id text NOT NULL REFERENCES vector_stores(id) ON DELETE CASCADE,
    file_id text NOT NULL REFERENCES files(id) ON DELETE CASCADE,

    external_user_id bigint NULL,
    api_key_id bigint NULL REFERENCES api_keys(id) ON DELETE SET NULL,

    status text NOT NULL DEFAULT 'attached',
    error text NULL,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz NULL,

    CONSTRAINT vector_store_files_status_check
        CHECK (status IN ('attached', 'processing', 'ready', 'failed', 'deleted'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_vector_store_files_active
ON vector_store_files(vector_store_id, file_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_vector_stores_external_user_id
ON vector_stores(external_user_id);

CREATE INDEX IF NOT EXISTS idx_vector_stores_api_key_id
ON vector_stores(api_key_id);

CREATE INDEX IF NOT EXISTS idx_vector_stores_status
ON vector_stores(status);

CREATE INDEX IF NOT EXISTS idx_vector_stores_created_at
ON vector_stores(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vector_stores_deleted_at
ON vector_stores(deleted_at);

CREATE INDEX IF NOT EXISTS idx_vector_store_files_vector_store_id
ON vector_store_files(vector_store_id);

CREATE INDEX IF NOT EXISTS idx_vector_store_files_file_id
ON vector_store_files(file_id);

CREATE INDEX IF NOT EXISTS idx_vector_store_files_external_user_id
ON vector_store_files(external_user_id);

CREATE INDEX IF NOT EXISTS idx_vector_store_files_api_key_id
ON vector_store_files(api_key_id);

CREATE INDEX IF NOT EXISTS idx_vector_store_files_status
ON vector_store_files(status);

CREATE INDEX IF NOT EXISTS idx_vector_store_files_created_at
ON vector_store_files(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vector_store_files_deleted_at
ON vector_store_files(deleted_at);

COMMIT;
