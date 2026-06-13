CREATE TABLE IF NOT EXISTS api_key_quota_ledger (
    id BIGSERIAL PRIMARY KEY,

    api_key_id BIGINT NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    external_user_id BIGINT,

    amount BIGINT NOT NULL,
    balance_after BIGINT NOT NULL,

    type TEXT NOT NULL,
    reason TEXT,
    reference_id TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_key_quota_ledger_key_id
ON api_key_quota_ledger(api_key_id);

CREATE INDEX IF NOT EXISTS idx_api_key_quota_ledger_external_user_id
ON api_key_quota_ledger(external_user_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_api_key_quota_ledger_reference
ON api_key_quota_ledger(reference_id)
WHERE reference_id IS NOT NULL;
