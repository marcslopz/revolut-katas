import datetime
import uuid
from typing import Any

import psycopg
import psycopg.types.json

from main import ScheduledNotificationDto


def schedule_notification(
    conn: psycopg.Connection,
    payload: dict[str, Any],
    due_at: datetime.datetime,
) -> str:
    """Insert a new scheduled notification and return its id.

    set explicitly, and what the row's initial status should be.
    """
    scheduled_notification_id = uuid.uuid4()

    sql = """
       INSERT INTO scheduled_notifications (scheduled_notification_id, payload, due_at)
           VALUES (%(notification_id)s, %(payload)s, %(due_at)s)
    """

    with conn.cursor() as cur:
        cur.execute(
            sql,
            {
                "notification_id": scheduled_notification_id,
                "payload": psycopg.types.json.Jsonb(payload),
                "due_at": due_at,
            },
        )
    conn.commit()

    return str(scheduled_notification_id)


def cancel_notification(conn: psycopg.Connection, notification_id: str) -> None:
    """Cancel a scheduled notification.

    TODO: write an UPDATE statement that only transitions the row if it's
    still in a cancellable state. Think about how to express "check current
    state, then set it" as a SINGLE atomic SQL statement (a conditional
    UPDATE), rather than a separate SELECT followed by an UPDATE. Use
    `RETURNING` and check how many rows came back to know whether it worked.
    """
    sql = """
        UPDATE scheduled_notifications
        SET status = 'canceled'
        WHERE scheduled_notification_id = %(notification_id)s
            AND status IN ('pending', 'canceled')
        RETURNING status
    """

    with conn.cursor() as cur:
        cur.execute(
            sql, {"notification_id": notification_id}
        )  # TODO: pass the right parameters
        updated_rows = cur.fetchall()
        if not updated_rows:
            get_sql = """
                  SELECT status FROM scheduled_notifications
                    WHERE scheduled_notification_id = %(notification_id)s
                  """
            cur.execute(get_sql, {"notification_id": notification_id})
            selected_rows = cur.fetchall()
            if selected_rows:
                raise ValueError("cancel conflict")
            else:
                raise ValueError("scheduled notification not found")
    conn.commit()


def get_next_due(
    conn: psycopg.Connection, now: datetime.datetime
) -> ScheduledNotificationDto | None:
    """Atomically claim and return the next due, pending notification, or None.

    TODO: write a query that finds and claims the earliest-due, still-pending
    row that is actually due by `now` — in a way that's safe when multiple
    workers call this concurrently against the same table. Then transition
    its status within the same transaction before committing.
    """
    with conn.cursor() as cur:
        select_sql = """
            SELECT scheduled_notification_id FROM scheduled_notifications
                WHERE status = 'pending'
                    AND due_at <= %(now)s
                ORDER BY due_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
        """
        cur.execute(select_sql, {"now": now})  # TODO: pass the right parameters
        row = cur.fetchone()

        if row is None:
            conn.commit()
            return None

        # noinspection unresolved-references
        scheduled_notification_id = row[0]
        update_sql = """
            UPDATE scheduled_notifications
            SET status = 'running'
            WHERE scheduled_notification_id = %(scheduled_notification_id)s
            RETURNING payload, due_at, status, scheduled_notification_id 
        """
        cur.execute(
            update_sql, {"scheduled_notification_id": scheduled_notification_id}
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("pending notification not found")
        # noinspection unresolved-references
        dto = ScheduledNotificationDto(row[0], row[1], row[2], str(row[3]))


    conn.commit()
    return dto  # TODO: shape the return value from `row`
