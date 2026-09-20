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
CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    balance INTEGER NOT NULL CHECK (balance >= 0)
);

CREATE TABLE transfers (
    transfer_id UUID PRIMARY KEY,
    amount INTEGER NOT NULL CHECK ( amount > 0 ),
    from_account_id TEXT NOT NULL REFERENCES accounts(account_id),
    to_account_id TEXT NOT NULL REFERENCES accounts(account_id),
    CHECK (from_account_id != to_account_id)
);

