import threading
from dataclasses import dataclass, field


class NotEnoughProductQuantityException(Exception):
    pass


class ProductAlreadyExistsException(Exception):
    pass


class ProductNotFoundException(Exception):
    pass


class InvalidProductIdException(Exception):
    pass


class InvalidQuantityException(Exception):
    pass


@dataclass
class Product:
    _id: str
    available_quantity: int
    reserved_quantities: list[int] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def reserve_quantity(self, quantity: int) -> None:
        with self.lock:
            if self.available_quantity < quantity:
                raise NotEnoughProductQuantityException
            self.reserved_quantities.append(quantity)
            self.available_quantity -= quantity

    def get_available_quantity(self) -> int:
        with self.lock:
            return self.available_quantity


def validate_product_id(product_id):
    if not isinstance(product_id, str):
        raise InvalidProductIdException


def validate_quantity(available_quantity):
    if not isinstance(available_quantity, int) or available_quantity <= 0:
        raise InvalidQuantityException

class ProductService:
    def __init__(self, products: dict[str, Product] = None):
        if products is None:
            self._products: dict[str, Product] = {}
        self._products_lock = threading.Lock()

    def add_product(self, product_id: str, available_quantity: int) -> None:
        validate_product_id(product_id)
        validate_quantity(available_quantity)

        with self._products_lock:
            if product_id in self._products:
                raise ProductAlreadyExistsException
            self._products[product_id] = Product(product_id, available_quantity)

    def reserve_product_quantity(self, product_id: str, quantity: int) -> None:
        validate_product_id(product_id)
        validate_quantity(quantity)

        with self._products_lock:
            if product_id not in self._products:
                raise ProductNotFoundException
            product = self._products[product_id]

        product.reserve_quantity(quantity)
