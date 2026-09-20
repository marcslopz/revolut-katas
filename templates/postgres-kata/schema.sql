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

CREATE TABLE example_records (
    record_id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'active', 'canceled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (idempotency_key)
);

-- Supports "find records for an owner in a given status, most recent first"
CREATE INDEX idx_example_records_owner_status_created
    ON example_records (owner_id, status, created_at DESC);
