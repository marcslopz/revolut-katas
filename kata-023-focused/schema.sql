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

CREATE TABLE cases (
    case_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK ( status IN ('completed', 'unclaimed', 'claimed') ),
    priority INTEGER NOT NULL CHECK (priority >= 1 AND priority <= 3),
    created_at TIMESTAMPTZ NOT NULL,
    claimed_at TIMESTAMPTZ DEFAULT NULL,
    worker_id TEXT DEFAULT NULL
);


