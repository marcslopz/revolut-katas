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


def create_document(conn: psycopg.Connection, owner_id: str, title: str) -> str:
    """Plain insert + commit."""
    document_id = uuid.uuid4()
    sql = """
        INSERT INTO documents (id, owner_id, title, status)
        VALUES (%(document_id)s, %(owner_id)s, %(title)s, 'created')
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {"document_id": document_id, "owner_id": owner_id, "title": title},
        )
    conn.commit()
    return str(document_id)


def delete_document(conn: psycopg.Connection, document_id: str, actor_id: str, actor_role: str) -> None:
    """Conditional UPDATE as a single atomic statement — the check
    ('status is still pending') and the act (transition it) happen in one
    round trip to Postgres, so two concurrent callers can't both see
    'pending' and both think they won. Returns whether this call is the one
    that actually made the transition."""
    sql = """
        UPDATE documents
        SET status = 'deleted'
        WHERE id = %(document_id)s
            AND (owner_id = %(actor_id)s OR %(actor_role)s = 'admin')
        RETURNING id
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"document_id": document_id, "actor_id": actor_id, "actor_role": actor_role})
        updated = cur.fetchone() is not None
        if updated:
            conn.commit()
            return None
        sql = """
              SELECT id FROM documents
              WHERE id = %(document_id)s
              """
        cur.execute(sql, {"document_id": document_id})
        row = cur.fetchone()
        if row is None:
            conn.rollback()
            raise KeyError(f"Document with id {document_id} not found")
        else:
            conn.rollback()
            raise ValueError(f"Document deletion denied")
