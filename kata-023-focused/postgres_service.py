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
from datetime import datetime, timedelta
from typing import Any

import psycopg

from main import CaseDto, CLAIM_TTL_IN_SECONDS, CaseStatus, CasePriority


def add_case(
    conn: psycopg.Connection, case_id: str, priority: int, now: datetime | None = None
) -> None:
    """Plain insert + commit."""
    if now is None:
        now = datetime.now()
    sql = """
        INSERT INTO cases (case_id, status, priority, created_at)
        VALUES (%(case_id)s, 'unclaimed', %(priority)s, %(created_at)s)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            {"case_id": case_id, "priority": priority, "created_at": now},
        )
    conn.commit()


def claim_next_case(
    conn: psycopg.Connection, worker_id: str, now: datetime | None = None
) -> CaseDto | None:
    if now is None:
        now = datetime.now()
    now_minus_lease_ttl = now - timedelta(seconds=CLAIM_TTL_IN_SECONDS)
    sql = """
        SELECT case_id, priority, created_at
        FROM cases
            WHERE status in ('claimed', 'unclaimed') AND
                (claimed_at IS NULL OR %(now_minus_lease_ttl)s > claimed_at)
            ORDER BY priority, claimed_at NULLS FIRST
            LIMIT 1
        FOR UPDATE SKIP LOCKED
    """
    with conn.cursor() as cur:
        cur.execute(sql, {"now_minus_lease_ttl": now_minus_lease_ttl})
        row = cur.fetchone()
        if row is None:
            conn.commit()
            return None
        case_id , priority, created_at= row

        update_sql = """
            UPDATE cases
            SET status = 'claimed', worker_id = %(worker_id)s, claimed_at = %(now)s
                WHERE case_id = %(case_id)s
        """
        cur.execute(update_sql, {"case_id": case_id, "now": now, "worker_id": worker_id})
        conn.commit()
        return CaseDto(
            status=CaseStatus.CLAIMED.name.lower(),
            priority=CasePriority(priority).name.lower(),
            created_at=str(created_at),
            case_id=case_id,
            worker_id=worker_id,
            claimed_at=str(now),
        )


