import threading
import uuid
from dataclasses import dataclass, field


class ValidationException(Exception):
    pass


class InvalidStock(ValidationException):
    pass


class InvalidId(ValidationException):
    pass


class InvalidQuantity(ValidationException):
    pass


class ServiceException(Exception):
    pass


class ProductNotFound(ServiceException):
    pass


class ReservationNotFound(ServiceException):
    pass


class NotEnoughStock(ServiceException):
    pass


@dataclass
class Reservation:
    product_id: uuid.UUID
    quantity: int
    reservation_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class Product:
    stock: int
    reservations: dict[uuid.UUID, Reservation] = field(default_factory=dict)
    product_id: uuid.UUID = field(default_factory=uuid.uuid4)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        if not isinstance(self.stock, int) or self.stock < 0:
            raise InvalidStock(self.stock)

    def reserve_quantity(self, reservation: Reservation) -> None:
        with self.lock:
            if reservation.quantity > self.stock:
                raise NotEnoughStock(self.stock, reservation.quantity)
            self.stock -= reservation.quantity
            self.reservations[reservation.reservation_id] = reservation

    def release_reservation(self, reservation_uuid):
        with self.lock:
            if reservation_uuid not in self.reservations:
                raise ReservationNotFound(self.product_id, reservation_uuid)
            reservation = self.reservations[reservation_uuid]
            self.stock += reservation.quantity
            del self.reservations[reservation_uuid]

    def get_stock(self) -> int:
        with self.lock:
            return self.stock


def get_uuid_from_str(input_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(input_id))
    except ValueError:
        raise InvalidId(input_id)


def validate_quantity(quantity: int):
    if not isinstance(quantity, int) or quantity <= 0:
        raise InvalidQuantity(quantity)


class ProductService:
    def __init__(self):
        self._products: dict[uuid.UUID, Product] = {}
        self._lock = threading.Lock()

    def register_product(self, initial_stock: int) -> str:
        product = Product(initial_stock)
        with self._lock:
            self._products[product.product_id] = product
        return str(product.product_id)

    def reserve_product(self, product_id: str, quantity: int) -> str:
        product_uuid = get_uuid_from_str(product_id)
        validate_quantity(quantity)
        with self._lock:
            if product_uuid not in self._products:
                raise ProductNotFound(product_id)
            product = self._products[product_uuid]
        reservation = Reservation(product_uuid, quantity)
        product.reserve_quantity(reservation)
        return str(reservation.reservation_id)

    def get_product_current_stock(self, product_id: str) -> int:
        product_uuid = get_uuid_from_str(product_id)
        with self._lock:
            if product_uuid not in self._products:
                raise ProductNotFound(product_id)
            product = self._products[product_uuid]
        return product.get_stock()

    def release_reservation(self, product_id: str, reservation_id: str) -> None:
        product_uuid = get_uuid_from_str(product_id)
        reservation_uuid = get_uuid_from_str(reservation_id)

        with self._lock:
            if product_uuid not in self._products:
                raise ProductNotFound(product_id)
            product = self._products[product_uuid]
        product.release_reservation(reservation_uuid)
