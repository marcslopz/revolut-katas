import dataclasses
import datetime
import threading

BUCKET_CAP_REQUEST = 5.0
TOKENS_PER_SECOND = 5


@dataclasses.dataclass
class Bucket:
    client_id: str
    available_tokens: float
    last_computed_time: datetime.datetime
    lock: threading.Lock = dataclasses.field(default_factory=threading.Lock)

    def allow_request(self, now: datetime.datetime) -> bool:
        with self.lock:
            delta_time = now - self.last_computed_time
            self.available_tokens = (
                min(
                    self.available_tokens
                    + TOKENS_PER_SECOND * delta_time.total_seconds(),
                    BUCKET_CAP_REQUEST,
                )
                - 1
            )
            self.last_computed_time = now
            if self.available_tokens < 0:
                self.available_tokens = 0
                return False
            return True


class RateLimiterService:
    def __init__(self):
        self._requests: dict[str, Bucket] = {}
        self._lock = threading.Lock()

    def allow_request(
        self, client_id: str, now: datetime.datetime | None = None
    ) -> bool:
        if now is None:
            now = datetime.datetime.now()
        with self._lock:
            if client_id not in self._requests:
                self._requests[client_id] = Bucket(client_id, BUCKET_CAP_REQUEST, now)
            bucket = self._requests[client_id]
        return bucket.allow_request(now)
