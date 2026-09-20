-- Generic Postgres schema template for kata practice.
--
-- Copy this file into a kata directory and replace `example_records` with
-- your actual domain table(s). Keep the patterns, adapt the shape:
--   - UUID primary key
--   - NOT NULL on everything that must always have a value
--   - a `status` CHECK constraint instead of a free-text column
--   - a UNIQUE constraint wherever the domain needs an idempotency key or
--     a "only one of X" invariant
--   - a composite index shaped for the query you actually run: equality
--     columns first, then the range/order column last
CREATE table deliveries (
    id TEXT PRIMARY KEY,
    partner_id TEXT NOT NULL,
    next_attempt_at TIMESTAMPTZ NOT NULL CHECK (next_attempt_at >= updated_at),
    updated_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK ( status IN ('pending', 'success', 'failed', 'running', 'canceled') ),
    attempts INTEGER NOT NULL DEFAULT 0
);

-- Supports "find records for an owner in a given status, most recent first"
CREATE INDEX idx_deliveries_next_attempt_at
    ON deliveries (status, next_attempt_at ASC)
