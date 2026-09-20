import datetime
import heapq
import threading
from dataclasses import dataclass, field
from enum import StrEnum, auto

MAX_RETRIES = 5


def validate_id(input_str: str):
    if not isinstance(input_str, str) or not input_str:
        raise ValueError(input_str)


def validate_next_attempt_at(
    next_attempt_at: datetime.datetime, now: datetime.datetime
):
    if not isinstance(next_attempt_at, datetime.datetime) or next_attempt_at < now:
        raise ValueError(next_attempt_at, now)


class Status(StrEnum):
    PENDING = auto()
    SUCCESS = auto()
    FAILED = auto()
    RUNNING = auto()
    CANCELED = auto()


@dataclass(frozen=True)
class DeliveryDto:
    delivery_id: str
    partner_id: str
    next_attempt_at: datetime.datetime
    attempts: int
    status: str


@dataclass(frozen=True, order=True)
class OrderedDeliveryDto:
    next_attempt_at: datetime.datetime
    disambiguation_count: int
    delivery_id: str = field(compare=False)


@dataclass
class Delivery:
    delivery_id: str
    partner_id: str
    next_attempt_at: datetime.datetime
    attempts: int = 0
    status: Status = Status.PENDING

    def __post_init__(self):
        validate_id(self.delivery_id)
        validate_id(self.partner_id)

    def cancel(self):
        if self.status not in (Status.PENDING, Status.CANCELED):
            raise ValueError(
                f"Can't cancel delivery {self.delivery_id}, status is {self.status}"
            )
        self.status = Status.CANCELED

    def to_dto(self) -> DeliveryDto:
        return DeliveryDto(
            self.delivery_id,
            self.partner_id,
            self.next_attempt_at,
            self.attempts,
            str(self.status),
        )

    def to_ordered_dto(self, disambiguation_count: int) -> OrderedDeliveryDto:
        return OrderedDeliveryDto(
            self.next_attempt_at, disambiguation_count, self.delivery_id
        )

    def increment_attempts(self):
        if self.attempts == MAX_RETRIES:
            raise ValueError(
                f"max retry attempts reached for delivery {self.delivery_id}"
            )
        self.attempts += 1


class RetryQueue:
    def __init__(self):
        self._deliveries: dict[str, Delivery] = dict()
        self._ordered_deliveries: list[OrderedDeliveryDto] = list()
        self._disambiguation_count: int = 0
        self._lock = threading.Lock()

    def schedule(
        self,
        delivery_id: str,
        partner_id: str,
        next_attempt_at: datetime.datetime,
        now: datetime.datetime | None = None,
    ):
        if now is None:
            now = datetime.datetime.now()
        validate_next_attempt_at(next_attempt_at, now)
        with self._lock:
            if delivery_id in self._deliveries:
                delivery = self._deliveries[delivery_id]
                delivery.next_attempt_at = next_attempt_at
                delivery.status = Status.PENDING
            else:
                delivery = Delivery(delivery_id, partner_id, next_attempt_at)
                self._deliveries[delivery_id] = delivery
            heapq.heappush(
                self._ordered_deliveries,
                delivery.to_ordered_dto(self._disambiguation_count),
            )
            self._disambiguation_count += 1

    def cancel(self, delivery_id: str) -> None:
        with self._lock:
            if delivery_id not in self._deliveries:
                raise ValueError(f"Delivery {delivery_id} not found")
            delivery = self._deliveries[delivery_id]
            delivery.cancel()

    def poll_due(self, now: datetime.datetime | None = None) -> DeliveryDto | None:
        if now is None:
            now = datetime.datetime.now()
        with self._lock:
            if len(self._ordered_deliveries) == 0:
                return None
            earliest_delivery_scheduled_at = self._ordered_deliveries[0].next_attempt_at
            if earliest_delivery_scheduled_at > now:
                return None
            while len(self._ordered_deliveries) > 0:
                delivery_ordered_dto = heapq.heappop(self._ordered_deliveries)
                if delivery_ordered_dto.next_attempt_at > now:
                    heapq.heappush(self._ordered_deliveries, delivery_ordered_dto)
                    return None
                delivery = self._deliveries[delivery_ordered_dto.delivery_id]
                if delivery.status != Status.PENDING:
                    continue
                if delivery.next_attempt_at != delivery_ordered_dto.next_attempt_at:
                    continue
                try:
                    delivery.increment_attempts()
                except ValueError:
                    delivery.status = Status.FAILED
                    continue
                return delivery.to_dto()
        return None
