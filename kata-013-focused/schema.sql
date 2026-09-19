-- TODO: write your schema here.
--
-- You need at least a table for scheduled notifications, holding whatever
-- columns the Python service needs to schedule/cancel/claim them (id, payload,
-- due_at, status, created_at, ...).
--
-- Think about:
--   - what type due_at should be, and what index supports "find the earliest
--     due, still-pending row" cheaply as the table grows
--   - what values status can take, and how you'll constrain it
--   - what should be UNIQUE, NOT NULL, or have a DEFAULT
CREATE TABLE scheduled_notifications(
    scheduled_notification_id UUID PRIMARY KEY,
    payload JSONB NOT NULL,
    due_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'canceled', 'failed', 'succeeded')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (due_at > created_at)
);

CREATE INDEX idx_scheduled_notification_status_due_at ON scheduled_notifications(status, due_at)

