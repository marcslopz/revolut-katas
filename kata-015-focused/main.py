import threading
import time
import uuid
from dataclasses import dataclass, field

RETRIES = 5
BACKOFF_CONSTANT_SECONDS = 1


class ConflictVersion(Exception):
    pass


class FailedShouldRetry(Exception):
    pass


@dataclass
class Purchase:
    sku_id: str
    buyer_id: str
    purchase_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class Sku:
    sku_id: str
    stock: int
    version: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        if self.stock < 0:
            raise ValueError("Stock cannot be negative")

    def purchase(self, version: int) -> None:
        with self.lock:
            if self.version != version:
                raise ConflictVersion(self.sku_id, self.version, version)
            if self.stock == 0:
                raise ValueError("Out of stock")
            self.stock -= 1
            self.version += 1


def _retry_operation(sku, operation_func, *args, **kwargs):
    for _ in range(RETRIES):
        try:
            operation_func(sku, *args, **kwargs)
            return
        except ConflictVersion:
            _backoff()
    raise FailedShouldRetry(sku.sku_id, operation_func)


def _backoff():
    time.sleep(BACKOFF_CONSTANT_SECONDS)


class FlashSaleService:
    def __init__(self):
        self._skus: dict[str, Sku] = {}
        self._purchases_by_sku_id: dict[str, list[Purchase]] = {}
        self._purchases_lock = threading.Lock()

    def create_sku(self, sku_id: str, stock: int) -> None:
        sku = Sku(sku_id, stock)
        self._skus[sku_id] = sku

    def _purchase(self, sku, buyer_id: str) -> None:
        sku_version = sku.version

        sku.purchase(sku_version)
        sku_id = sku.sku_id
        with self._purchases_lock:
            if sku_id not in self._purchases_by_sku_id:
                self._purchases_by_sku_id[sku_id] = []
            self._purchases_by_sku_id[sku_id].append(Purchase(sku.sku_id, buyer_id))


    def purchase_sku(self, sku_id: str, buyer_id: str) -> None:
        sku = self._skus[sku_id]
        _retry_operation(sku, self._purchase, buyer_id)
