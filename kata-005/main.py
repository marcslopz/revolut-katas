import threading
from dataclasses import dataclass, field


class ServiceException(Exception):
    pass


class AlreadyExistingClient(ServiceException):
    pass


class ClientNotFound(ServiceException):
    pass


class ValidationException(Exception):
    pass


class InvalidClientId(ValidationException):
    pass


class InvalidQuota(ValidationException):
    pass


class AlreadyExistingClient(ServiceException):
    pass

@dataclass
class ClientDto:
    client_id: str
    quota: int
    current_requests: int
@dataclass
class Client:
    client_id: str
    quota: int
    current_requests: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record_request(self) -> bool:
        with self.lock:
            if self.current_requests >= self.quota:
                return False
            else:
                self.current_requests += 1
                return True

    def to_dto(self) -> ClientDto:
        return ClientDto(self.client_id, self.quota, self.current_requests)


def validate_client_id(client_id):
    if not isinstance(client_id, str) or not client_id:
        raise InvalidClientId


def validate_quota(quota):
    if not isinstance(quota, int) or quota <= 0:
        raise InvalidQuota


class ClientQuotaService:
    def __init__(self):
        self._clients: dict[str, Client] = dict()
        self._lock = threading.Lock()

    def create_client(self, client_id: str, quota: int) -> None:
        validate_client_id(client_id)
        validate_quota(quota)
        with self._lock:
            if client_id in self._clients:
                raise AlreadyExistingClient(client_id)
            self._clients[client_id] = Client(client_id, quota)

    def record_client_request(self, client_id: str) -> bool:
        validate_client_id(client_id)
        with self._lock:
            if client_id not in self._clients:
                raise ClientNotFound
            client = self._clients[client_id]
            was_record_allowed = client.record_request()
        return was_record_allowed

    def get_client(self, client_id: str) -> ClientDto:
        validate_client_id(client_id)
        with self._lock:
            if client_id not in self._clients:
                raise ClientNotFound
            client = self._clients[client_id]
            client_dto = client.to_dto()
        return client_dto
