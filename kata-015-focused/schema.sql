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
CREATE TABLE skus (
    sku_id TEXT NOT NULL PRIMARY KEY,
    stock INTEGER NOT NULL CHECK (stock >= 0),
    version INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE purchases (
    purchase_id UUID PRIMARY KEY,
    sku_id TEXT NOT NULL REFERENCES skus(sku_id),
    buyer_id TEXT NOT NULL
);


-- Supports "find records for an owner in a given status, most recent first"
CREATE INDEX idx_purchases_sku_id
    ON purchases (sku_id);
