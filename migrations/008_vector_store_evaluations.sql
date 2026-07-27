BEGIN;

CREATE TABLE IF NOT EXISTS vector_store_chunks (
    vector_store_id TEXT NOT NULL REFERENCES vector_stores(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    api_key_id BIGINT NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunking_strategy TEXT NOT NULL,
    chunking_version TEXT NOT NULL,
    embedding_version TEXT,
    character_count INTEGER NOT NULL,
    token_count INTEGER,
    exact_hash VARCHAR(64) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (vector_store_id, id)
);

CREATE INDEX IF NOT EXISTS idx_vector_store_chunks_owner
ON vector_store_chunks(api_key_id, vector_store_id);

CREATE INDEX IF NOT EXISTS idx_vector_store_chunks_file
ON vector_store_chunks(vector_store_id, file_id);

CREATE INDEX IF NOT EXISTS idx_vector_store_chunks_exact_hash
ON vector_store_chunks(vector_store_id, exact_hash);

CREATE TABLE IF NOT EXISTS evaluation_datasets (
    id TEXT PRIMARY KEY,
    api_key_id BIGINT NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    vector_store_id TEXT NOT NULL REFERENCES vector_stores(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'ready',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT evaluation_datasets_status_check
        CHECK (status IN ('ready', 'archived')),
    CONSTRAINT evaluation_datasets_owner_name_version_unique
        UNIQUE (api_key_id, vector_store_id, name, version)
);

CREATE INDEX IF NOT EXISTS idx_evaluation_datasets_owner
ON evaluation_datasets(api_key_id, vector_store_id, created_at DESC);

CREATE TABLE IF NOT EXISTS evaluation_cases (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    gold_chunk_ids TEXT[] NOT NULL,
    paraphrases TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    language VARCHAR(32),
    intent VARCHAR(100),
    rarity VARCHAR(32),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT evaluation_cases_gold_chunks_not_empty
        CHECK (cardinality(gold_chunk_ids) > 0)
);

CREATE INDEX IF NOT EXISTS idx_evaluation_cases_dataset
ON evaluation_cases(dataset_id, created_at);

CREATE TABLE IF NOT EXISTS vector_store_evaluation_runs (
    id TEXT PRIMARY KEY,
    api_key_id BIGINT NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    vector_store_id TEXT NOT NULL REFERENCES vector_stores(id) ON DELETE CASCADE,
    dataset_id TEXT NOT NULL REFERENCES evaluation_datasets(id) ON DELETE RESTRICT,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary JSONB,
    evaluator_version VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT vector_store_evaluation_runs_type_check
        CHECK (type IN ('semantic_coverage')),
    CONSTRAINT vector_store_evaluation_runs_status_check
        CHECK (status IN ('queued', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_vector_store_evaluation_runs_owner
ON vector_store_evaluation_runs(api_key_id, vector_store_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_vector_store_evaluation_runs_status
ON vector_store_evaluation_runs(status, created_at);

CREATE TABLE IF NOT EXISTS vector_store_evaluation_results (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES vector_store_evaluation_runs(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL REFERENCES evaluation_cases(id) ON DELETE CASCADE,
    metric VARCHAR(100) NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    severity VARCHAR(20) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT vector_store_evaluation_results_severity_check
        CHECK (severity IN ('info', 'warning', 'critical')),
    CONSTRAINT vector_store_evaluation_results_run_case_metric_unique
        UNIQUE (run_id, case_id, metric)
);

CREATE INDEX IF NOT EXISTS idx_vector_store_evaluation_results_run
ON vector_store_evaluation_results(run_id, id);

COMMIT;
