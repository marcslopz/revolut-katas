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

CREATE TABLE buckets (
    client_id TEXT PRIMARY KEY,
    available_tokens NUMERIC NOT NULL DEFAULT 5 CHECK (available_tokens >= 0 and available_tokens <= 5),
    last_computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

