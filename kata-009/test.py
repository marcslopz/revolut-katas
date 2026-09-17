import concurrent.futures
import threading
import uuid

import pytest

from main import (
    ProductService,
    InvalidStock,
    ProductNotFound,
    InvalidQuantity,
    NotEnoughStock,
    ReservationNotFound,
    InvalidId,
)


def test_register_product():
    service = ProductService()

    product_id = service.register_product(0)

    assert service.get_product_current_stock(product_id) == 0


@pytest.mark.parametrize("initial_stock", [-1, "invalid", None])
def test_register_product_invalid_stock(initial_stock):
    service = ProductService()

    with pytest.raises(InvalidStock):
        service.register_product(initial_stock)


def test_reserve_product():
    service = ProductService()
    product_id = service.register_product(1)

    service.reserve_product(product_id, 1)

    assert service.get_product_current_stock(product_id) == 0


@pytest.mark.parametrize("quantity", [-1, 0, "invalid", None])
def test_reserve_product_invalid_quantity(quantity):
    service = ProductService()
    product_id = service.register_product(1)

    with pytest.raises(InvalidQuantity):
        service.reserve_product(product_id, quantity)


def test_reserve_product_not_found():
    service = ProductService()
    service.register_product(1)

    with pytest.raises(ProductNotFound):
        service.reserve_product(str(uuid.uuid4()), 1)


def test_reserve_product_not_enough_stock():
    service = ProductService()
    product_id = service.register_product(1)

    with pytest.raises(NotEnoughStock):
        service.reserve_product(product_id, 2)


def test_get_product_current_stock_not_found():
    service = ProductService()
    service.register_product(1)

    with pytest.raises(ProductNotFound):
        service.get_product_current_stock(str(uuid.uuid4()))


def test_release_reservation():
    service = ProductService()
    product_id = service.register_product(1)
    reservation_id = service.reserve_product(product_id, 1)

    service.release_reservation(product_id, reservation_id)

    assert service.get_product_current_stock(product_id) == 1


def test_release_reservation_product_not_found():
    service = ProductService()
    service.register_product(1)
    with pytest.raises(ProductNotFound):
        service.release_reservation(str(uuid.uuid4()), str(uuid.uuid4()))


def test_release_reservation_reservation_not_found():
    service = ProductService()
    product_id = service.register_product(1)

    with pytest.raises(ReservationNotFound):
        service.release_reservation(product_id, str(uuid.uuid4()))


@pytest.mark.parametrize(
    "product_id, reservation_id",
    [
        (None, uuid.uuid4()),
        ("invalid_uuid", uuid.uuid4()),
        (2, uuid.uuid4()),
        (uuid.uuid4(), None),
        (uuid.uuid4(), "invalid_uuid"),
        (uuid.uuid4(), 2),
    ],
)
def test_release_reservation_product_invalid_ids(product_id, reservation_id):
    service = ProductService()
    with pytest.raises(InvalidId):
        service.release_reservation(product_id, reservation_id)

def test_concurrent_reservations():
    service = ProductService()
    product_id = service.register_product(2)
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)

    def worker():
        barrier.wait()
        try:
            service.reserve_product(product_id, 1)
            return True
        except NotEnoughStock:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=number_of_threads) as executor:
        futures = [executor.submit(worker) for _ in range(number_of_threads)]
        results = [future.result() for future in futures]

    assert len(results) == number_of_threads
    assert results.count(True) == 2
    assert results.count(False) == number_of_threads - 2