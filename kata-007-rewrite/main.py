import datetime
import threading
import uuid
from dataclasses import dataclass, field

class ServiceException(Exception):
    pass
class RoomNotFound(ServiceException):
    pass
class UserNotFound(ServiceException):
    pass
class BookingNotFound(ServiceException):
    pass
class CancelConflict(ServiceException):
    pass
class BookingOverlap(ServiceException):
    pass
class InvalidBookingId(ServiceException):
    pass



@dataclass(frozen=True)
class BookingDto:
    room_id: str
    user_id: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    booking_id: str

@dataclass
class Booking:
    room_id: str
    user_id: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    booking_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def check_overlap(self, start_time, end_time):
        if max(start_time, self.start_time) < min(end_time, self.end_time):
            raise BookingOverlap(self.room_id, self.user_id, start_time, end_time)

    def to_dto(self) -> BookingDto:
        return BookingDto(self.room_id, self.user_id, self.start_time, self.end_time, str(self.booking_id))


class BookingService:
    def __init__(self):
        self._bookings: dict[uuid.UUID, Booking] = {}
        self._bookings_by_room: dict[str, set[uuid.UUID]] = {}
        self._bookings_by_user: dict[str, set[uuid.UUID]] = {}
        self._idempotency_keys: dict[str, uuid.UUID] = {}
        self._lock = threading.Lock()

    def create_booking(self, idempotency_key: str, room_id: str, user_id: str, start_time: datetime.datetime, end_time: datetime.datetime) -> str:
        with self._lock:
            booking = Booking(room_id, user_id, start_time, end_time)
            if idempotency_key in self._idempotency_keys:
                return str(self._idempotency_keys[idempotency_key])
            if room_id not in self._bookings_by_room:
                self._bookings_by_room[room_id] = set()
            if user_id not in self._bookings_by_user:
                self._bookings_by_user[user_id] = set()
            for current_booking_id in self._bookings_by_room[room_id]:
                current_booking = self._bookings[current_booking_id]
                current_booking.check_overlap(start_time, end_time)
            self._bookings[booking.booking_id] = booking
            self._bookings_by_room[room_id].add(booking.booking_id)
            self._bookings_by_user[user_id].add(booking.booking_id)
            self._idempotency_keys[idempotency_key] = booking.booking_id

        return str(booking.booking_id)

    def list_room_bookings(self, room_id: str) -> list[BookingDto]:
        with self._lock:
            if room_id not in self._bookings_by_room:
                raise RoomNotFound(room_id)
            booking_ids = self._bookings_by_room[room_id]
            booking_dtos = [self._bookings[booking_id].to_dto() for booking_id in booking_ids]

        return booking_dtos

    def list_user_bookings(self, user_id: str) -> list[BookingDto]:
        with self._lock:
            if user_id not in self._bookings_by_user:
                raise UserNotFound(user_id)
            booking_ids = self._bookings_by_user[user_id]
            booking_dtos = [self._bookings[booking_id].to_dto() for booking_id in booking_ids]

        return booking_dtos

    def cancel_booking(self, booking_id: str, room_id: str, user_id: str) -> None:
        with self._lock:
            try:
                booking_uuid = uuid.UUID(str(booking_id))
            except ValueError:
                raise InvalidBookingId(booking_id)
            if booking_uuid not in self._bookings:
                raise BookingNotFound(booking_id)
            if room_id not in self._bookings_by_room:
                raise RoomNotFound(room_id)
            if user_id not in self._bookings_by_user:
                raise UserNotFound(user_id)
            booking = self._bookings[booking_uuid]
            if booking.user_id != user_id or booking.room_id != room_id:
                raise CancelConflict(booking_id, room_id, user_id)
            room_bookings = self._bookings_by_room[room_id]
            room_bookings.remove(booking_uuid)
            user_bookings = self._bookings_by_user[user_id]
            user_bookings.remove(booking_uuid)
            del self._bookings[booking_uuid]


