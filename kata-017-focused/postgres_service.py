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
import decimal

import psycopg


def allow_request(
    conn: psycopg.Connection, client_id: str, now: datetime.datetime | None = None
) -> bool:
    if now is None:
        now = datetime.datetime.now()
    """Plain insert + commit."""
    sql = """
        INSERT INTO buckets (client_id, last_computed_at) 
        VALUES (%(client_id)s, %(last_computed_at)s)
            ON CONFLICT (client_id) DO 
            UPDATE SET client_id = EXCLUDED.client_id
            RETURNING available_tokens, last_computed_at
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"client_id": client_id, "last_computed_at": now})
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            raise ValueError(f"Upsert failed for client {client_id}")
        available_tokens, last_computed_at = row
        delta_time = now - last_computed_at
        new_available_tokens = (
            min(
                available_tokens + 5 * decimal.Decimal(str(delta_time.total_seconds())),
                5,
            )
            - 1
        )
        if new_available_tokens < 0:
            new_available_tokens = 0
            return_value = False
        else:
            return_value = True
        update_sql = """
            UPDATE buckets SET available_tokens = %(new_available_tokens)s, last_computed_at = %(last_computed_at)s
                WHERE client_id = %(client_id)s
                RETURNING available_tokens, last_computed_at
        """
        cur.execute(
            update_sql,
            {
                "new_available_tokens": new_available_tokens,
                "last_computed_at": now,
                "client_id": client_id,
            },
        )
        updated = cur.fetchone()
        if updated is None:
            conn.rollback()
            raise ValueError(f"Update failed for client {client_id}")
        conn.commit()
    return return_value
