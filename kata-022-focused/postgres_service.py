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

import dataclasses
import datetime
import uuid

import psycopg


def apply_card_action(conn: psycopg.Connection, card_id: str, new_status: str) -> None:
    """Plain insert + commit."""
    sql = """
        UPDATE cards
         SET status = %(status)s
             WHERE card_id = %(card_id)s
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {"card_id": card_id, "status": new_status},
        )
        event_id = uuid.uuid4()
        insert_event_sql = """
            INSERT INTO events (event_id, status, card_id, card_action)
                VALUES (%(event_id)s, 'not_delivered', %(card_id)s, %(card_action)s)
        """
        cur.execute(
            insert_event_sql,
            {
                "card_id": card_id,
                "event_id": event_id,
                "card_action": "freeze" if new_status == "frozen" else "unfreeze",
            },
        )

    conn.commit()


from main import CLAIM_TTL_IN_SECONDS


@dataclasses.dataclass(frozen=True)
class EventDto:
    event_id: uuid.UUID
    status: str
    card_id: str
    card_action: str


def claim_next_event(
    conn: psycopg.Connection, now: datetime.datetime | None = None
) -> EventDto | None:
    """Insert relying on the UNIQUE constraint on idempotency_key. On a
    conflict, explicitly rolls back the failed statement (required before
    the connection can run anything else) and returns the id of the row
    that already exists instead of raising."""
    if now is None:
        now = datetime.datetime.now()
    now_minus_ttl = now - datetime.timedelta(seconds=CLAIM_TTL_IN_SECONDS)
    sql = """
        SELECT event_id, status, card_id, card_action from events 
        WHERE 
            status IN ('not_delivered', 'claimed') AND 
            (claimed_at is NULL OR claimed_at < %(now_minus_ttl)s)
        ORDER BY claimed_at NULLS FIRST
            LIMIT 1
        FOR UPDATE SKIP LOCKED
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {
                "now_minus_ttl": now_minus_ttl,
            },
        )
        row = cur.fetchone()
        if row is None:
            conn.commit()
            return None
        event_id, status, card_id, card_action = row
        event_dto = EventDto(event_id, status, card_id, card_action)

        update_sql = """
            UPDATE events
            SET status = 'claimed', claimed_at = %(now)s
                WHERE event_id = %(event_id)s
        """
        cur.execute(update_sql, {"now": now, "event_id": event_id})

        conn.commit()
        return event_dto
