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


def create_sku(conn: psycopg.Connection, sku_id: str, stock: int) -> None:
    """Plain insert + commit."""
    sql = """
        INSERT INTO skus (sku_id, stock)
        VALUES (%(sku_id)s, %(stock)s)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {"sku_id": sku_id, "stock": stock},
        )
    conn.commit()


def purchase_sku(conn: psycopg.Connection, sku_id: str, buyer_id: str) -> None:
    """Conditional UPDATE as a single atomic statement — the check
    ('status is still pending') and the act (transition it) happen in one
    round trip to Postgres, so two concurrent callers can't both see
    'pending' and both think they won. Returns whether this call is the one
    that actually made the transition."""
    sql = """
        SELECT stock, version
        FROM skus
            WHERE sku_id = %(sku_id)s
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"sku_id": sku_id})
        row = cur.fetchone()
        if row is None:
            conn.commit()
            raise ValueError(f"Not Found {sku_id}")
        if row[0] == 0:
            conn.commit()
            raise ValueError(f"Not enough stock for {sku_id}")

        version = row[1]
        decrement_stock_qsl = """
            UPDATE skus
            SET stock = stock - 1, version = %(version)s + 1 WHERE sku_id = %(sku_id)s and version = %(version)s
                RETURNING stock
        """
        cur.execute(decrement_stock_qsl, {"sku_id": sku_id, "version": version})
        updated = cur.fetchone()
        if updated is None:
            conn.commit()
            raise ValueError(f"Conflict on purchase, need to retry for {sku_id}")

        purchase_id = uuid.uuid4()
        add_purchase_qsl = """
            INSERT INTO purchases (purchase_id, sku_id, buyer_id)
                VALUES (%(purchase_id)s, %(sku_id)s, %(buyer_id)s)
                RETURNING purchase_id
        """
        cur.execute(
            add_purchase_qsl,
            {"purchase_id": purchase_id, "sku_id": sku_id, "buyer_id": buyer_id},
        )
        inserted = cur.fetchone()
        if inserted is None:
            conn.rollback()
            raise ValueError(f"Error inserting purchase for {sku_id}")

    conn.commit()
