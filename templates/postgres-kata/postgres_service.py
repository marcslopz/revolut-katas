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

import uuid
from typing import Any

import psycopg


def create_record(conn: psycopg.Connection, owner_id: str, idempotency_key: str) -> str:
    """Plain insert + commit."""
    record_id = uuid.uuid4()
    sql = """
        INSERT INTO example_records (record_id, owner_id, idempotency_key)
        VALUES (%(record_id)s, %(owner_id)s, %(idempotency_key)s)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {"record_id": record_id, "owner_id": owner_id, "idempotency_key": idempotency_key},
        )
    conn.commit()
    return str(record_id)


def create_record_idempotent(conn: psycopg.Connection, owner_id: str, idempotency_key: str) -> str:
    """Insert relying on the UNIQUE constraint on idempotency_key. On a
    conflict, explicitly rolls back the failed statement (required before
    the connection can run anything else) and returns the id of the row
    that already exists instead of raising."""
    record_id = uuid.uuid4()
    insert_sql = """
        INSERT INTO example_records (record_id, owner_id, idempotency_key)
        VALUES (%(record_id)s, %(owner_id)s, %(idempotency_key)s)
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                insert_sql,
                {"record_id": record_id, "owner_id": owner_id, "idempotency_key": idempotency_key},
            )
        conn.commit()
        return str(record_id)
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        select_sql = "SELECT record_id FROM example_records WHERE idempotency_key = %(idempotency_key)s"
        with conn.cursor() as cur:
            cur.execute(select_sql, {"idempotency_key": idempotency_key})
            row = cur.fetchone()
        return str(row[0])


def activate_record(conn: psycopg.Connection, record_id: str) -> bool:
    """Conditional UPDATE as a single atomic statement — the check
    ('status is still pending') and the act (transition it) happen in one
    round trip to Postgres, so two concurrent callers can't both see
    'pending' and both think they won. Returns whether this call is the one
    that actually made the transition."""
    sql = """
        UPDATE example_records
        SET status = 'active'
        WHERE record_id = %(record_id)s
            AND status = 'pending'
        RETURNING record_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"record_id": record_id})
        updated = cur.fetchone() is not None
    conn.commit()
    return updated


def activate_record_with_transaction_block(conn: psycopg.Connection, record_id: str) -> bool:
    """Same transition, using psycopg3's `conn.transaction()` context
    manager instead of manual commit()/rollback(): it commits on a clean
    exit and rolls back automatically if the block raises. Prefer this over
    manual commit/rollback once more than one statement has to succeed or
    fail together."""
    sql = """
        UPDATE example_records
        SET status = 'active'
        WHERE record_id = %(record_id)s
            AND status = 'pending'
        RETURNING record_id
    """
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(sql, {"record_id": record_id})
            updated = cur.fetchone() is not None
    return updated


def get_record(conn: psycopg.Connection, record_id: str) -> dict[str, Any] | None:
    sql = "SELECT record_id, owner_id, status FROM example_records WHERE record_id = %(record_id)s"
    with conn.cursor() as cur:
        cur.execute(sql, {"record_id": record_id})
        row = cur.fetchone()
    if row is None:
        return None
    return {"record_id": str(row[0]), "owner_id": str(row[1]), "status": row[2]}
