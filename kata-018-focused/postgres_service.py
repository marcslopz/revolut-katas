"""Example insert/update/commit/rollback patterns with psycopg3, against the
`example_records` table in schema.sql. Copy into a kata directory and adapt
to the actual domain/table — keep the patterns:

- every query below is parameterized (%(name)s placeholders bound via the
  second argument to `execute`) — never build SQL by interpolating values
  into the query string, that's a SQL injection hole.
- a state transition is a single conditional UPDATE ... RETURNING, not a
  SELECT to check the state followed by a separate UPDATE (that's a
  check-then-act race under concurrent callers).
"""

import datetime

import psycopg


def schedule(
    conn: psycopg.Connection,
    delivery_id: str,
    partner_id: str,
    next_attempt_at: datetime.datetime,
    now: datetime.datetime | None = None,
) -> None:
    """Plain insert + commit."""
    if now is None:
        now = datetime.datetime.now()
    sql = """
        INSERT INTO deliveries (id, partner_id, next_attempt_at, updated_at, status, attempts)
        VALUES (%(delivery_id)s, %(partner_id)s, %(next_attempt_at)s, %(now)s, 'pending', 0) ON CONFLICT(id) DO UPDATE 
            SET status = 'pending', attempts = deliveries.attempts, next_attempt_at = %(next_attempt_at)s, updated_at = %(now)s
            RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {
                "delivery_id": delivery_id,
                "partner_id": partner_id,
                "next_attempt_at": next_attempt_at,
                "now": now,
            },
        )
    conn.commit()


from main import DeliveryDto, MAX_RETRIES


def poll_due(
    conn: psycopg.Connection, now: datetime.datetime | None = None
) -> DeliveryDto | None:
    if now is None:
        now = datetime.datetime.now()
    sql = """
        SELECT id, partner_id, next_attempt_at, attempts
        FROM deliveries
            WHERE status = 'pending' AND next_attempt_at <= %(now)s
            ORDER BY next_attempt_at
            LIMIT 1
            FOR UPDATE SKIP LOCKED
    """
    with conn.cursor() as cur:
        while True:
            cur.execute(
                sql,
                {
                    "now": now,
                },
            )
            row = cur.fetchone()
            if row is None:
                # no more due deliveries
                conn.commit()
                return None
            delivery_id, partner_id, next_attempt_at, attempts = row
            if attempts == MAX_RETRIES:
                # max retries, reached, update status and select the next due
                update_failed_status_sql = """
                    UPDATE deliveries
                    SET status = 'failed'
                        WHERE id = %(delivery_id)s
                """
                cur.execute(
                    update_failed_status_sql,
                    {
                        "delivery_id": delivery_id,
                    },
                )
                continue
            increment_attempts_sql = """
                UPDATE deliveries
                SET attempts = attempts + 1, status = 'running'
                    WHERE id = %(delivery_id)s
            """
            cur.execute(
                increment_attempts_sql,
                {
                    "delivery_id": delivery_id,
                },
            )
            conn.commit()
            return DeliveryDto(
                delivery_id, partner_id, next_attempt_at, attempts + 1, "running"
            )

        conn.commit()
        return None
