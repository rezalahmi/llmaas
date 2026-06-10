CREATE TABLE IF NOT EXISTS user_daily_usage (
    id BIGSERIAL PRIMARY KEY,
    external_user_id BIGINT NOT NULL,
    usage_date DATE NOT NULL,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT user_daily_usage_unique UNIQUE (external_user_id, usage_date)
);

CREATE TABLE IF NOT EXISTS user_usage_snapshot (
    external_user_id BIGINT PRIMARY KEY,
    last_total BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_daily_usage_user_date
ON user_daily_usage (external_user_id, usage_date);
