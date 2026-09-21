import dataclasses
import datetime
import enum
import heapq
import threading
import uuid

CLAIM_TTL_IN_SECONDS = 60


class CardStatus(enum.StrEnum):
    FROZEN = enum.auto()
    UNFROZEN = enum.auto()


@dataclasses.dataclass
class Card:
    card_id: str
    status: CardStatus

    def freeze(self) -> None:
        self.status = CardStatus.FROZEN

    def unfreeze(self) -> None:
        self.status = CardStatus.UNFROZEN


class EventStatus(enum.IntEnum):
    DELIVERED = enum.auto()
    NOT_DELIVERED = enum.auto()
    CLAIMED = enum.auto()


@dataclasses.dataclass(frozen=True)
class EventDto:
    claimed_at: datetime.datetime
    event_id: uuid.UUID
    status: str


@dataclasses.dataclass(order=True)
class Event:
    status: EventStatus = EventStatus.NOT_DELIVERED
    claimed_at: datetime.datetime = datetime.datetime.min
    event_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)

    def claim_is_not_expired(self, now):
        return self.claimed_at + datetime.timedelta(seconds=CLAIM_TTL_IN_SECONDS) >= now


class CardStatusService:
    def __init__(self):
        self._cards_by_id: dict[str, Card] = {}
        self._events_by_id: dict[uuid.UUID, Event] = {}
        self._ordered_events: list[Event] = []
        self._lock = threading.Lock()

    def _insert_event(self, event: Event) -> None:
        self._events_by_id[event.event_id] = event
        heapq.heappush(self._ordered_events, event)

    def add_card(self, card_id: str, status: CardStatus = CardStatus.UNFROZEN) -> None:
        with self._lock:
            if card_id in self._cards_by_id:
                raise ValueError("Card already exists", card_id)
            self._cards_by_id[card_id] = Card(card_id, status)

    def freeze_card(self, card_id: str) -> uuid.UUID:
        with self._lock:
            if card_id not in self._cards_by_id:
                raise KeyError("Card not found", card_id)
            self._cards_by_id[card_id].freeze()
            event = Event()
            self._insert_event(event)
            return event.event_id

    def unfreeze_card(self, card_id: str) -> uuid.UUID:
        with self._lock:
            if card_id not in self._cards_by_id:
                raise KeyError("Card not found", card_id)
            self._cards_by_id[card_id].unfreeze()
            event = Event()
            self._insert_event(event)
            return event.event_id

    def claim_next_event(self, now: datetime.datetime | None = None) -> EventDto | None:
        if now is None:
            now = datetime.datetime.now()
        with self._lock:
            if not self._ordered_events:
                return None
            while self._ordered_events:
                next_event = heapq.heappop(self._ordered_events)
                if next_event.status == EventStatus.DELIVERED:
                    continue
                if next_event.status == EventStatus.CLAIMED:
                    if next_event.claim_is_not_expired(now):
                        heapq.heappush(self._ordered_events, next_event)
                        return None
                    else:
                        next_event.claimed_at = now
                        heapq.heappush(self._ordered_events, next_event)
                        return EventDto(
                            next_event.claimed_at,
                            next_event.event_id,
                            next_event.status.name.lower(),
                        )
                next_event.claimed_at = now
                next_event.status = EventStatus.CLAIMED
                heapq.heappush(self._ordered_events, next_event)
                return EventDto(
                    next_event.claimed_at,
                    next_event.event_id,
                    next_event.status.name.lower(),
                )
        return None

    def mark_delivered(self, event_id: uuid.UUID) -> None:
        with self._lock:
            if event_id not in self._events_by_id:
                raise KeyError("Event not found", event_id)
            self._events_by_id[event_id].status = EventStatus.DELIVERED
