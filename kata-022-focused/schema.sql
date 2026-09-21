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
CREATE TABLE cards
(
    card_id TEXT PRIMARY KEY,
    status  TEXT NOT NULL CHECK ( status IN ('frozen', 'unfrozen') )
);

CREATE TABLE events
(
    event_id    UUID PRIMARY KEY,
    status      TEXT NOT NULL CHECK ( status IN ('not_delivered', 'delivered', 'claimed') ),
    claimed_at  TIMESTAMPTZ DEFAULT NULL,
    card_id     TEXT NOT NULL REFERENCES cards (card_id),
    card_action TEXT NOT NULL CHECK ( card_action IN ('freeze', 'unfreeze') )
);

CREATE INDEX idx_events_status_claimed_at
    ON events (status, claimed_at);
