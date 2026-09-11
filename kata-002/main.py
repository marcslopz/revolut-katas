import threading
import uuid
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


class ReservationNotFoundException(Exception):
    pass


from enum import StrEnum


class ReservationStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


@dataclass
class Reservation:
    quantity: int
    _id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: ReservationStatus = ReservationStatus.PENDING

    def __str__(self):
        return str(self._id)

    def is_not_releasable(self) -> bool:
        return self.status != ReservationStatus.PENDING


class ReservationNotReleasable(Exception):
    pass


@dataclass
class Product:
    _id: str
    available_quantity: int
    reservations: dict[str, Reservation] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def reserve_quantity(self, quantity: int) -> str:
        with self.lock:
            if self.available_quantity < quantity:
                raise NotEnoughProductQuantityException
            reservation = Reservation(quantity)
            reservation_id = str(reservation)
            self.reservations[reservation_id] = reservation
            self.available_quantity -= quantity
            return reservation_id

    def release_quantity(self, reservation_id: str) -> None:
        with self.lock:
            if reservation_id not in self.reservations:
                raise ReservationNotFoundException
            reservation = self.reservations[reservation_id]
            if reservation.is_not_releasable():
                raise ReservationNotReleasable
            self.available_quantity += self.reservations[reservation_id].quantity
            del self.reservations[reservation_id]

    def get_available_quantity(self) -> int:
        with self.lock:
            return self.available_quantity

    def confirm_reservation(self, reservation_id):
        with self.lock:
            if reservation_id not in self.reservations:
                raise ReservationNotFoundException
            reservation = self.reservations[reservation_id]
            reservation.status = ReservationStatus.CONFIRMED


def validate_product_id(product_id):
    if not isinstance(product_id, str):
        raise InvalidProductIdException


class InvalidReservationIdException(Exception):
    pass


def validate_reservation_id(reservation_id):
    if not isinstance(reservation_id, str):
        raise InvalidReservationIdException


def validate_quantity(available_quantity):
    if not isinstance(available_quantity, int) or available_quantity <= 0:
        raise InvalidQuantityException


class ProductService:
    def __init__(self, products: dict[str, Product] = None):
        if products is None:
            self._products: dict[str, Product] = {}
        else:
            self._products: dict[str, Product] = products
        self._products_lock = threading.Lock()

    def add_product(self, product_id: str, available_quantity: int) -> None:
        validate_product_id(product_id)
        validate_quantity(available_quantity)

        with self._products_lock:
            if product_id in self._products:
                raise ProductAlreadyExistsException
            self._products[product_id] = Product(product_id, available_quantity)

    def reserve_product_quantity(self, product_id: str, quantity: int) -> str:
        validate_product_id(product_id)
        validate_quantity(quantity)

        with self._products_lock:
            if product_id not in self._products:
                raise ProductNotFoundException
            product = self._products[product_id]

        return product.reserve_quantity(quantity)

    def release_product_reservation(self, product_id: str, reservation_id: str) -> None:
        validate_product_id(product_id)
        validate_reservation_id(reservation_id)

        with self._products_lock:
            if product_id not in self._products:
                raise ProductNotFoundException
            product = self._products[product_id]

        product.release_quantity(reservation_id)

    def confirm_product_reservation(self, product_id: str, reservation_id: str) -> None:
        validate_product_id(product_id)
        validate_reservation_id(reservation_id)

        with self._products_lock:
            if product_id not in self._products:
                raise ProductNotFoundException
            product = self._products[product_id]

        product.confirm_reservation(reservation_id)
