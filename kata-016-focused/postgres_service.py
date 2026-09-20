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

import psycopg


def create_account(conn: psycopg.Connection, account_id: str, balance: int) -> None:
    """Plain insert + commit."""
    sql = """
        INSERT INTO accounts (account_id, balance)
        VALUES (%(account_id)s, %(balance)s)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {"account_id": account_id, "balance": balance},
        )
    conn.commit()


def transfer(
    conn: psycopg.Connection, from_account_id: str, to_account_id: str, amount: int
) -> None:
    """Conditional UPDATE as a single atomic statement — the check
    ('status is still pending') and the act (transition it) happen in one
    round trip to Postgres, so two concurrent callers can't both see
    'pending' and both think they won. Returns whether this call is the one
    that actually made the transition."""
    if from_account_id == to_account_id:
        raise ValueError(
            f"Transfer denied, same account id {from_account_id}, {to_account_id}"
        )
    first_account_id = (
        from_account_id if from_account_id < to_account_id else to_account_id
    )
    second_account_id = (
        to_account_id if from_account_id < to_account_id else from_account_id
    )
    claim_lock_sql = """
        SELECT balance
        FROM accounts
            WHERE account_id = %(account_id)s
            FOR UPDATE
    """
    with conn.cursor() as cur:
        for account_id in (first_account_id, second_account_id):
            cur.execute(claim_lock_sql, {"account_id": account_id})
            row = cur.fetchone()
            if row is None:
                conn.rollback()
                raise ValueError(f"Account nof found {account_id}")

        update_from_account_sql = """
            UPDATE accounts
            SET balance = balance - %(amount)s
                WHERE account_id = %(account_id)s
            RETURNING balance
        """
        try:
            cur.execute(
                update_from_account_sql, {"amount": amount, "account_id": from_account_id}
            )
        except psycopg.IntegrityError:
            conn.rollback()
            raise ValueError(f"Not enough balance for account {from_account_id}")

        updated = cur.fetchone()
        if updated is None:
            conn.rollback()
            raise ValueError(
                f"Transfer from account {from_account_id} couldn't be done"
            )

        update_to_account_sql = """
                                  UPDATE accounts
                                  SET balance = balance + %(amount)s
                                  WHERE account_id = %(account_id)s
                                  RETURNING balance
                                  """
        cur.execute(
            update_to_account_sql, {"amount": amount, "account_id": to_account_id}
        )
        updated = cur.fetchone()
        if updated is None:
            conn.rollback()
            raise ValueError(f"Transfer to account {to_account_id} couldn't be done")

        transfer_id = uuid.uuid4()
        insert_transfer_sql = """
            INSERT INTO transfers (transfer_id, amount, from_account_id, to_account_id)
                VALUES (%(transfer_id)s, %(amount)s, %(from_account_id)s, %(to_account_id)s)
        """
        cur.execute(
            insert_transfer_sql,
            {
                "transfer_id": transfer_id,
                "amount": amount,
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
            },
        )
    conn.commit()
