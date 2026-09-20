"""Connection + schema apply/reset helpers. Copy into a kata directory as-is
(no domain-specific logic lives here — that goes in postgres_service.py).

Usage:
    python db.py apply   # run schema.sql against the local database
    python db.py reset   # drop everything in the public schema, empty it
"""

import sys

import psycopg

DSN = "host=localhost port=5432 dbname=kata user=kata password=kata"


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DSN)


def apply_schema(conn: psycopg.Connection, schema_path: str = "schema.sql") -> None:
    with open(schema_path) as f:
        schema_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()


def reset_database(conn: psycopg.Connection) -> None:
    """Drop every table/index/sequence in the public schema and recreate it
    empty. Use this between kata sessions instead of hand-picking tables to
    truncate/drop."""
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE")
        cur.execute("CREATE SCHEMA public")
    conn.commit()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "apply"
    connection = get_connection()
    try:
        if action == "apply":
            apply_schema(connection)
        elif action == "reset":
            reset_database(connection)
        else:
            raise SystemExit(f"unknown action {action!r}, use 'apply' or 'reset'")
    finally:
        connection.close()
