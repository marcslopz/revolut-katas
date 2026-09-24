import threading


class ServiceException(Exception):
    pass


class UsernameTaken(ServiceException):
    pass


class UsernameNotFound(ServiceException):
    pass


class RegisterService:
    def __init__(self) -> None:
        self._users_by_name: set[str] = set()
        self._lock: threading.Lock = threading.Lock()
    def register(self, username: str) -> None:
        with self._lock:
            if username in self._users_by_name:
                raise UsernameTaken()
            self._users_by_name.add(username)

    def release(self, username: str) -> None:
        with self._lock:
            if username not in self._users_by_name:
                raise UsernameNotFound(username)
            self._users_by_name.remove(username)

    def is_taken(self, username: str) -> bool:
        with self._lock:
            return username in self._users_by_name
