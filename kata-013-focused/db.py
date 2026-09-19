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


def reset_schema(conn: psycopg.Connection, table_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table_name}")
    conn.commit()
