import datetime
import threading
from dataclasses import dataclass, field

class ServiceException(Exception):
    pass
class BookingConflict(ServiceException):
    pass
class RoomBookingsNotFound(ServiceException):
    pass

@dataclass
@dataclass
class RoomBookings:
    room_id: str
    bookings: list[tuple[datetime.datetime, datetime.datetime]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_booking(self, start: datetime.datetime, end: datetime.datetime) -> None:
        with self.lock:
            for current_start, current_end in self.bookings:
                if max(current_start, start) < min(current_end, end):
                    raise BookingConflict(self.room_id, start, end)
            self.bookings.append((start, end))

    def list_bookings(self):
        with self.lock:
            bookings_list = list(self.bookings)
        return bookings_list


class RoomBookingService:
    def __init__(self) -> None:
        self._room_bookings: dict[str, RoomBookings] = dict()
        self._lock = threading.Lock()

    def create_booking(self, room_id: str, start: datetime.datetime, end: datetime.datetime) -> None:
        with self._lock:
            if room_id not in self._room_bookings:
                self._room_bookings[room_id] = RoomBookings(room_id, list([(start, end)]))
                return
            room_bookings = self._room_bookings[room_id]
        room_bookings.add_booking(start, end)

    def list_bookings(self, room_id: str) -> list[tuple[datetime.datetime, datetime.datetime]]:
        with self._lock:
            if room_id not in self._room_bookings:
                raise RoomBookingsNotFound(room_id)
            room_bookings = self._room_bookings[room_id]
        return room_bookings.list_bookings()