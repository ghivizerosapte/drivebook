-- 005_fix_rate_limit.sql
-- The original rate_limit_buckets had bucket_key as sole PRIMARY KEY,
-- but services.py uses ON CONFLICT (bucket_key, window_start) which
-- requires a UNIQUE constraint on both columns. Rebuild the table.

DROP TABLE IF EXISTS rate_limit_buckets;

CREATE TABLE rate_limit_buckets (
    id           BIGSERIAL PRIMARY KEY,
    bucket_key   TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    count        INT NOT NULL DEFAULT 1,
    UNIQUE (bucket_key, window_start)
);

CREATE INDEX IF NOT EXISTS rl_key_window_idx
    ON rate_limit_buckets (bucket_key, window_start DESC);
