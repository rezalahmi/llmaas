BEGIN;

CREATE TABLE IF NOT EXISTS vector_store_chunks (
    vector_store_id TEXT NOT NULL
        REFERENCES vector_stores(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    api_key_id BIGINT NOT NULL
        REFERENCES api_keys(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL
        REFERENCES files(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    chunking_strategy TEXT NOT NULL,
    chunking_version TEXT NOT NULL,
    embedding_version TEXT,
    character_count INTEGER NOT NULL CHECK (character_count >= 0),
    token_count INTEGER CHECK (token_count IS NULL OR token_count >= 0),
    exact_hash VARCHAR(64) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (vector_store_id, id),
    UNIQUE (vector_store_id, file_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_vector_store_chunks_owner
ON vector_store_chunks(api_key_id, vector_store_id);

CREATE INDEX IF NOT EXISTS idx_vector_store_chunks_file
ON vector_store_chunks(vector_store_id, file_id);

CREATE INDEX IF NOT EXISTS idx_vector_store_chunks_exact_hash
ON vector_store_chunks(vector_store_id, exact_hash);

COMMIT;
