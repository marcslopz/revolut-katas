import dataclasses
import datetime
import heapq
import threading
import uuid
from enum import StrEnum, auto
from typing import Any


class ValidationException(Exception):
    pass


class InvalidDueAt(ValidationException):
    pass


class InvalidUuid(ValidationException):
    pass


class ServiceException(Exception):
    pass


class ScheduledNotificationNotFound(ServiceException):
    pass


class CancelConflict(ServiceException):
    pass


class Status(StrEnum):
    PENDING = auto()
    RUNNING = auto()
    CANCELED = auto()
    FAILED = auto()
    SUCCEEDED = auto()


@dataclasses.dataclass(frozen=True, order=True)
class ScheduledNotificationHeapElement:
    due_at: datetime.datetime
    tiebreak_counter: int
    scheduled_notification_id: uuid.UUID = dataclasses.field(compare=False)


@dataclasses.dataclass(frozen=True)
class ScheduledNotificationDto:
    payload: dict[str, Any]
    due_at: datetime.datetime
    status: str
    scheduled_notification_id: str


@dataclasses.dataclass
class ScheduledNotification:
    payload: dict[str, Any]
    due_at: datetime.datetime
    created_at: datetime.datetime
    status: Status = Status.PENDING
    scheduled_notification_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)
    status_lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)

    def __post_init__(self):
        if self.due_at < self.created_at:
            raise InvalidDueAt(self.due_at)

    def cancel(self):
        with self.status_lock:
            if self.status not in (Status.CANCELED, Status.PENDING):
                raise CancelConflict(self.scheduled_notification_id)
            self.status = Status.CANCELED

    def to_heap_element(self, tiebreak_counter) -> ScheduledNotificationHeapElement:
        return ScheduledNotificationHeapElement(
            self.due_at, tiebreak_counter, self.scheduled_notification_id
        )

    def to_dto(self) -> ScheduledNotificationDto:
        with self.status_lock:
            return ScheduledNotificationDto(
                self.payload,
                self.due_at,
                str(self.status),
                str(self.scheduled_notification_id),
            )

    def try_claim_running(self) -> bool:
        with self.status_lock:
            if self.status != Status.PENDING:
                return False
            self.status = Status.RUNNING
            return True


def get_uuid_from_str(uuid_str):
    try:
        return uuid.UUID(str(uuid_str))
    except ValueError:
        raise InvalidUuid(uuid_str)


class ScheduledNotificationService:
    def __init__(self):
        self._scheduled_notifications: dict[uuid.UUID, ScheduledNotification] = {}
        self._ordered_scheduled_notifications: list[
            ScheduledNotificationHeapElement
        ] = []
        self._tiebreak_counter = 1
        self._lock = threading.Lock()

    def schedule_notification(
        self,
        payload: dict[str, Any],
        due_at: datetime.datetime,
        now: datetime.datetime | None = None,
    ) -> str:
        if not now:
            now = datetime.datetime.now()
        scheduled_notification = ScheduledNotification(payload, due_at, created_at=now)
        with self._lock:
            self._scheduled_notifications[
                scheduled_notification.scheduled_notification_id
            ] = scheduled_notification
            heapq.heappush(
                self._ordered_scheduled_notifications,
                scheduled_notification.to_heap_element(self._tiebreak_counter),
            )
            self._tiebreak_counter += 1
        return str(scheduled_notification.scheduled_notification_id)

    def cancel_scheduled_notification(self, scheduled_notification_id: str) -> None:
        scheduled_notification_uuid = get_uuid_from_str(scheduled_notification_id)
        with self._lock:
            scheduled_notification = self._get_scheduled_notification_by_id(
                scheduled_notification_uuid
            )
        scheduled_notification.cancel()

    def _get_scheduled_notification_by_id(
        self, scheduled_notification_uuid
    ) -> ScheduledNotification:
        if scheduled_notification_uuid not in self._scheduled_notifications:
            raise ScheduledNotificationNotFound(scheduled_notification_uuid)
        return self._scheduled_notifications[scheduled_notification_uuid]

    def _pop_next_scheduled_notification(self) -> ScheduledNotification | None:
        if not self._ordered_scheduled_notifications:
            return None
        earliest_sched_notification = heapq.heappop(
            self._ordered_scheduled_notifications
        )
        return self._get_scheduled_notification_by_id(
            earliest_sched_notification.scheduled_notification_id
        )

    def get_next_due(self, now: datetime.datetime) -> ScheduledNotificationDto | None:
        with self._lock:
            if not self._ordered_scheduled_notifications:
                return None
            earliest_sched_notification = self._ordered_scheduled_notifications[0]
            if earliest_sched_notification.due_at > now:
                return None
            scheduled_notification = self._pop_next_scheduled_notification()
            if scheduled_notification is not None and scheduled_notification.due_at > now:
                return None
            while (
                scheduled_notification is not None
                and not scheduled_notification.try_claim_running()
            ):
                scheduled_notification = self._pop_next_scheduled_notification()
                if scheduled_notification is not None and scheduled_notification.due_at > now:
                    return None
            if not scheduled_notification:
                return None
        return scheduled_notification.to_dto()
