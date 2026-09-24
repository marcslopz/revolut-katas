import dataclasses
import threading


class ValidationException(Exception):
    pass


class InvalidStock(ValidationException):
    pass


class InvalidSku(ValidationException):
    pass


class InvalidQuantity(ValidationException):
    pass


class ServiceException(Exception):
    pass


class NotEnoughStock(ServiceException):
    pass


class AlreadyExistingSku(ServiceException):
    pass


class SkuNotFound(ServiceException):
    pass


def validate_sku(sku):
    if not isinstance(sku, str) or not sku:
        raise InvalidSku(sku)


@dataclasses.dataclass
class Product:
    sku: str
    stock: int

    def __post_init__(self):
        if not isinstance(self.stock, int) or self.stock < 0:
            raise InvalidStock(self.stock)
        validate_sku(self.sku)

    def deduct(self, quantity):
        if quantity > self.stock:
            raise NotEnoughStock(self.sku, self.stock, quantity)
        self.stock -= quantity


def validate_quantity(quantity):
    if not isinstance(quantity, int) or quantity <= 0:
        raise InvalidQuantity(quantity)


class InventoryService:
    def __init__(self) -> None:
        self._stock_by_sku: dict[str, Product] = {}
        self._lock = threading.Lock()

    def add_sku(self, sku: str, stock: int) -> None:
        with self._lock:
            if sku in self._stock_by_sku:
                raise AlreadyExistingSku(sku)
            self._stock_by_sku[sku] = Product(sku, stock)

    def deduct_stock(self, sku: str, quantity: int) -> None:
        validate_quantity(quantity)
        with self._lock:
            if sku not in self._stock_by_sku:
                raise SkuNotFound(sku)
            self._stock_by_sku[sku].deduct(quantity)

    def get_stock(self, sku: str) -> int:
        validate_sku(sku)
        with self._lock:
            if sku not in self._stock_by_sku:
                raise SkuNotFound(sku)
            return self._stock_by_sku[sku].stock
