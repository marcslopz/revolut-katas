import dataclasses
import datetime
import enum
import threading
import uuid


class ServiceException(Exception):
    pass


class UnknownSeatId(ServiceException):
    pass


class ReservationNotFound(ServiceException):
    pass


class WrongCustomerIdForRelease(ServiceException):
    pass


class ReservationAlreadyReleased(ServiceException):
    pass


class SeatAlreadyHeld(ServiceException):
    pass


class EmptySeatSet(ServiceException):
    pass


class SeatStatus(enum.StrEnum):
    FREE = enum.auto()
    HELD = enum.auto()


class ReservationStatus(enum.StrEnum):
    LOCKED = enum.auto()
    RELEASED = enum.auto()


TTL_IN_SECONDS = 300


def is_expired(now: datetime.datetime, timestamp_to_check: datetime.datetime) -> bool:
    return timestamp_to_check + datetime.timedelta(seconds=TTL_IN_SECONDS) < now


@dataclasses.dataclass
class Seat:
    seat_id: str
    held_at: datetime.datetime = dataclasses.field(default=datetime.datetime.min)
    held_by: str | None = None
    status: SeatStatus = SeatStatus.FREE

    def hold(self, customer_id, now: datetime.datetime) -> None:
        if self.status == self.status.HELD:
            if not is_expired(now, self.held_at):
                raise SeatAlreadyHeld(customer_id)
            else:
                self.held_at = now
        self.status = SeatStatus.HELD
        self.held_by = customer_id
        self.held_at = now

    def free(self):
        self.status = SeatStatus.FREE
        self.held_by = None
        self.held_at = datetime.datetime.min

    def get_status_with_ttl(self, now):
        if self.status == SeatStatus.FREE:
            return self.status
        return SeatStatus.FREE if is_expired(now, self.held_at) else SeatStatus.HELD


@dataclasses.dataclass
class Reservation:
    seat_ids: set[str]
    customer_id: str
    reserved_at: datetime.datetime
    status: ReservationStatus = ReservationStatus.LOCKED
    reservation_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)

    def release(self, customer_id) -> set[str]:
        if self.status != self.status.LOCKED:
            raise ReservationAlreadyReleased(self.reservation_id)
        if self.customer_id != customer_id:
            raise WrongCustomerIdForRelease(customer_id)
        self.reserved_at = datetime.datetime.min
        self.status = ReservationStatus.RELEASED
        return self.seat_ids

    def get_status_with_ttl(self, now: datetime.datetime) -> str:
        if self.status == ReservationStatus.RELEASED:
            return self.status
        return (
            ReservationStatus.RELEASED
            if is_expired(now, self.reserved_at)
            else ReservationStatus.LOCKED
        )


class ReservationSeatService:
    def __init__(self, initial_seat_ids: set[str]):
        self._reservations_by_id: dict[uuid.UUID, Reservation] = {}
        self._seats_by_id: dict[str, Seat] = {
            seat_id: Seat(seat_id) for seat_id in initial_seat_ids
        }
        self._lock = threading.Lock()

    def hold_seats(
        self, customer_id: str, seat_ids: set[str], now: datetime.datetime | None = None
    ) -> uuid.UUID:
        if not seat_ids:
            raise EmptySeatSet
        with self._lock:
            if any(seat_id not in self._seats_by_id for seat_id in seat_ids):
                raise UnknownSeatId(seat_ids)
            if now is None:
                now = datetime.datetime.now()
            reservation = Reservation(seat_ids, customer_id, now)
            already_held = set()
            try:
                for seat_id in seat_ids:
                    self._seats_by_id[seat_id].hold(customer_id, now)
                    already_held.add(seat_id)
            except SeatAlreadyHeld:
                for seat_id in already_held:
                    self._seats_by_id[seat_id].free()
                raise SeatAlreadyHeld
            self._reservations_by_id[reservation.reservation_id] = reservation
            return reservation.reservation_id

    def release_reservation(self, customer_id: str, reservation_id: uuid.UUID) -> None:
        with self._lock:
            if reservation_id not in self._reservations_by_id:
                raise ReservationNotFound(reservation_id)
            reservation = self._reservations_by_id[reservation_id]
            seat_ids = reservation.release(customer_id)
            for seat_id in seat_ids:
                self._seats_by_id[seat_id].free()

    def get_seat_status(
        self, seat_id: str, now: datetime.datetime | None = None
    ) -> str:
        with self._lock:
            if seat_id not in self._seats_by_id:
                raise UnknownSeatId(seat_id)
            if now is None:
                now = datetime.datetime.now()
            return self._seats_by_id[seat_id].get_status_with_ttl(now)

    def get_reservation_status(
        self, reservation_id: uuid.UUID, now: datetime.datetime | None = None
    ) -> str:
        with self._lock:
            if reservation_id not in self._reservations_by_id:
                raise ReservationNotFound(reservation_id)
            if now is None:
                now = datetime.datetime.now()
            return self._reservations_by_id[reservation_id].get_status_with_ttl(now)
