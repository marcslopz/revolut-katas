import datetime
import threading
import uuid
from dataclasses import dataclass, field


class ServiceException(Exception):
    pass


class BookingConflict(ServiceException):
    pass


class RoomBookingsNotFound(ServiceException):
    pass

class RoomBookingNotFound(ServiceException):
    pass

class RoomBookingCancelConflict(ServiceException):
    pass


@dataclass
class Booking:
    start: datetime.datetime
    end: datetime.datetime
    booking_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __eq__(self, other):
        if isinstance(other, Booking):
            return self.booking_id == other.booking_id
        return str(self.booking_id) == other


@dataclass
class RoomBookings:
    room_id: str
    user_id: str
    bookings: list[Booking] = field(
        default_factory=list
    )
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_booking(self, booking: Booking) -> None:
        with self.lock:
            for current_booking in self.bookings:
                if max(current_booking.start, booking.start) < min(current_booking.end, booking.end):
                    raise BookingConflict(self.room_id, booking.start, booking.end)
            self.bookings.append(booking)

    def list_bookings(self) -> list[Booking]:
        with self.lock:
            bookings_list = list(self.bookings)
        return bookings_list

    def cancel_booking(self, booking_id):
        with self.lock:
            self.bookings.remove(booking_id)


@dataclass
class UserBookings:
    user_id: str
    bookings: list[Booking] = field(
        default_factory=list
    )
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_booking(
        self, booking: Booking
    ) -> None:
        with self.lock:
            self.bookings.append(booking)

    def list_bookings(self):
        with self.lock:
            bookings_list = list(self.bookings)
        return bookings_list

    def cancel_booking(self, booking_id):
        with self.lock:
            self.bookings.remove(booking_id)


class RoomBookingService:
    def __init__(self) -> None:
        self._room_bookings: dict[str, RoomBookings] = dict()
        self._user_bookings: dict[str, UserBookings] = dict()
        self._bookings_by_id: dict[str, tuple[Booking, str, str]] = dict()
        self._lock = threading.Lock()

    def create_booking(
        self,
        room_id: str,
        user_id: str,
        start: datetime.datetime,
        end: datetime.datetime,
    ) -> str:
        booking = Booking(start, end)
        with self._lock:
            if room_id not in self._room_bookings:
                self._room_bookings[room_id] = RoomBookings(
                    room_id, user_id, list([booking])
                )
                self._user_bookings[user_id] = UserBookings(
                    user_id, list([booking])
                )
                self._bookings_by_id[str(booking.booking_id)] = (booking, room_id, user_id)
                return str(booking.booking_id)
            room_bookings = self._room_bookings[room_id]
            user_bookings = self._user_bookings[user_id]

        room_bookings.add_booking(booking)
        user_bookings.add_booking(booking)
        return str(booking.booking_id)

    def list_bookings_by_room_id(
        self, room_id: str
    ) -> list[Booking]:
        with self._lock:
            if room_id not in self._room_bookings:
                raise RoomBookingsNotFound(room_id)
            room_bookings = self._room_bookings[room_id]
        return room_bookings.list_bookings()

    def list_bookings_by_user_id(
        self, user_id: str
    ) -> list[Booking]:
        with self._lock:
            if user_id not in self._user_bookings:
                raise RoomBookingsNotFound(user_id)
            room_bookings = self._user_bookings[user_id]
        return room_bookings.list_bookings()

    def cancel_booking(self, booking_id: str, room_id: str, user_id: str) -> None:
        with self._lock:
            if booking_id not in self._bookings_by_id:
                raise RoomBookingNotFound(booking_id)
            booking, booking_room_id, booking_user_id = self._bookings_by_id[booking_id]
            try:
                room_bookings = self._room_bookings[room_id]
                user_bookings = self._user_bookings[user_id]
            except KeyError:
                raise RoomBookingCancelConflict(room_id, user_id)

        room_bookings.cancel_booking(booking_id)
        user_bookings.cancel_booking(booking_id)

        with self._lock:
            del self._bookings_by_id[str(booking.booking_id)]

