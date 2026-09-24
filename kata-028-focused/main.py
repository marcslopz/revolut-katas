import threading


class ValidationException(Exception):
    pass


class ServiceException(Exception):
    pass


class SpotNotAvailable(ServiceException):
    pass


class ExceedCapacity(ServiceException):
    pass


class ParkingService:
    def __init__(self, capacity: int) -> None:
        self._spots = capacity
        self._capacity = capacity
        self._lock = threading.Lock()

    def enter(self) -> None:
        with self._lock:
            if self._spots == 0:
                raise SpotNotAvailable()
            self._spots -= 1

    def exit(self) -> None:
        with self._lock:
            if self._spots == self._capacity:
                raise ExceedCapacity()
            self._spots += 1

    def available_spots(self) -> int:
        with self._lock:
            return self._spots
