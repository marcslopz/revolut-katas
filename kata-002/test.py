import concurrent.futures
import threading

import pytest

from main import (
    ProductService,
    InvalidProductIdException,
    InvalidQuantityException,
    ProductAlreadyExistsException,
    ProductNotFoundException,
    NotEnoughProductQuantityException,
    ReservationNotFoundException,
    InvalidReservationIdException,
    ReservationStatus, ReservationNotReleasable,
)


def test_add_product_null_id():
    product_service = ProductService()

    with pytest.raises(InvalidProductIdException):
        product_service.add_product(None, 10)

    assert len(product_service._products) == 0


def test_add_product_already_exists():
    product_service = ProductService()
    product_service.add_product("product_1", 10)

    with pytest.raises(ProductAlreadyExistsException):
        product_service.add_product("product_1", 20)

    assert product_service._products["product_1"].get_available_quantity() == 10


def test_add_product_null_available_quantity():
    product_service = ProductService()

    with pytest.raises(InvalidQuantityException):
        product_service.add_product("product_1", None)

    assert len(product_service._products) == 0


def test_add_product_negative_available_quantity():
    product_service = ProductService()

    with pytest.raises(InvalidQuantityException):
        product_service.add_product("product_1", -1)

    assert len(product_service._products) == 0


def test_add_product_zero_available_quantity():
    product_service = ProductService()

    with pytest.raises(InvalidQuantityException):
        product_service.add_product("product_1", 0)

    assert len(product_service._products) == 0


def test_add_product_invalid_type_available_quantity():
    product_service = ProductService()

    with pytest.raises(InvalidQuantityException):
        product_service.add_product("product_1", "wrong_type")

    assert len(product_service._products) == 0


def test_add_product_invalid_type_id():
    product_service = ProductService()

    with pytest.raises(InvalidProductIdException):
        product_service.add_product(2, 10)

    assert len(product_service._products) == 0


def test_add_product_ok():
    product_service = ProductService()

    product_service.add_product("product_1", 10)

    assert len(product_service._products) == 1
    assert product_service._products["product_1"].available_quantity == 10
    assert product_service._products["product_1"].reservations == {}


def test_add_product_thread_safe():
    product_service = ProductService()
    barrier = threading.Barrier(3)

    def worker():
        barrier.wait()
        try:
            product_service.add_product("product_1", 10)
            return "success"
        except ProductAlreadyExistsException:
            return "error"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        barrier.wait()
        results = [future.result() for future in futures]

    assert results.count("success") == 1
    assert results.count("error") == 1


def test_reserve_product_quantity_id_not_found():
    product_service = ProductService()
    with pytest.raises(ProductNotFoundException):
        product_service.reserve_product_quantity("product_1", 10)


def test_reserve_product_quantity_invalid_type_id():
    product_service = ProductService()
    with pytest.raises(InvalidProductIdException):
        product_service.reserve_product_quantity(2, 10)


def test_reserve_product_quantity_invalid_type_quantity():
    product_service = ProductService()
    with pytest.raises(InvalidQuantityException):
        product_service.reserve_product_quantity("product_1", "wrong_type")


def test_reserve_product_quantity_negative_quantity():
    product_service = ProductService()
    with pytest.raises(InvalidQuantityException):
        product_service.reserve_product_quantity("product_1", -1)


def test_reserve_product_quantity_zero_quantity():
    product_service = ProductService()
    with pytest.raises(InvalidQuantityException):
        product_service.reserve_product_quantity("product_1", 0)


def test_reserve_product_quantity_ok():
    product_service = ProductService()
    product_service.add_product("product_1", 10)

    product_service.reserve_product_quantity("product_1", 9)

    assert product_service._products["product_1"].get_available_quantity() == 1


def test_reserve_product_all_available_quantity_ok():
    product_service = ProductService()
    product_service.add_product("product_1", 10)

    product_service.reserve_product_quantity("product_1", 10)

    assert product_service._products["product_1"].get_available_quantity() == 0


def test_reserve_product_not_enough_available_quantity_ok():
    product_service = ProductService()
    product_service.add_product("product_1", 10)

    with pytest.raises(NotEnoughProductQuantityException):
        product_service.reserve_product_quantity("product_1", 11)


def test_reserve_product_quantity_thread_safe():
    product_service = ProductService()
    product_service.add_product("product_1", 10)

    def worker():
        try:
            product_service.reserve_product_quantity("product_1", 10)
            return "success"
        except NotEnoughProductQuantityException:
            return "error"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        results = [future.result() for future in futures]

    assert results.count("success") == 1
    assert results.count("error") == 1

def test_release_product_reservation_invalid_product_id():
    product_service = ProductService()
    product_service.add_product("product_1", 10)
    reservation_id = product_service.reserve_product_quantity("product_1", 9)

    with pytest.raises(InvalidProductIdException):
        product_service.release_product_reservation(None, reservation_id)


def test_release_product_reservation_invalid_reservation_id():
    product_service = ProductService()
    product_service.add_product("product_1", 10)
    product_service.reserve_product_quantity("product_1", 9)

    with pytest.raises(InvalidReservationIdException):
        product_service.release_product_reservation("product_1", None)
        
def test_release_product_reservation_product_not_found():
    product_service = ProductService()
    product_service.add_product("product_1", 10)
    product_service.reserve_product_quantity("product_1", 9)

    with pytest.raises(ProductNotFoundException):
        product_service.release_product_reservation("product_2", "does not matter")

def test_release_product_reservation_reservation_not_found():
    product_service = ProductService()
    product_service.add_product("product_1", 10)
    product_service.reserve_product_quantity("product_1", 9)

    with pytest.raises(ReservationNotFoundException):
        product_service.release_product_reservation("product_1", "not found")



def test_release_product_reservation_ok():
    product_service = ProductService()
    product_service.add_product("product_1", 10)
    reservation_id = product_service.reserve_product_quantity("product_1", 9)
    
    product_service.release_product_reservation("product_1", reservation_id)
    
    assert product_service._products["product_1"].get_available_quantity() == 10
    
def test_release_product_reservation_thread_safe():
    product_service = ProductService()
    product_service.add_product("product_1", 10)
    reservation_id = product_service.reserve_product_quantity("product_1", 9)

    def worker():
        try:
            product_service.release_product_reservation("product_1", reservation_id)
            return "success"
        except ReservationNotFoundException:
            return "error"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        results = [future.result() for future in futures]

    assert results.count("success") == 1
    assert results.count("error") == 1
    
def test_confirm_product_reservation_ok():
    product_service = ProductService()
    product_service.add_product("product_1", 10)
    reservation_id = product_service.reserve_product_quantity("product_1", 9)
    
    product_service.confirm_product_reservation("product_1", reservation_id)
    
    assert product_service._products["product_1"].get_available_quantity() == 1
    assert product_service._products["product_1"].reservations[reservation_id].quantity == 9
    assert product_service._products["product_1"].reservations[reservation_id].status == ReservationStatus.CONFIRMED

def test_confirm_product_reservation_duplicated_ok():
    product_service = ProductService()
    product_service.add_product("product_1", 10)
    reservation_id = product_service.reserve_product_quantity("product_1", 9)
    product_service.confirm_product_reservation("product_1", reservation_id)
    product_service.confirm_product_reservation("product_1", reservation_id)

    assert product_service._products["product_1"].get_available_quantity() == 1
    assert (
        product_service._products["product_1"].reservations[reservation_id].quantity
        == 9
    )
    assert (
        product_service._products["product_1"].reservations[reservation_id].status
        == ReservationStatus.CONFIRMED
    )

def test_release_confirmed_reservation():
    product_service = ProductService()
    product_service.add_product("product_1", 10)
    reservation_id = product_service.reserve_product_quantity("product_1", 9)
    product_service.confirm_product_reservation("product_1", reservation_id)

    with pytest.raises(ReservationNotReleasable):
        product_service.release_product_reservation("product_1", reservation_id)
