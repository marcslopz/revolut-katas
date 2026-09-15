import concurrent.futures
import threading
import uuid

import pytest

from main import (
    PaymentService,
    InvalidIdempotencyKey,
    InvalidAmount,
    InvalidCurrency,
    PaymentNotFound, AmountOrCurrencyConflict,
)


def test_create_payment_ok():
    service = PaymentService()
    idempotency_key = str(uuid.uuid4())

    payment_id = service.create_payment(idempotency_key, 10, "EUR")

    payment = service.get_payment(payment_id)
    assert payment.amount == 10
    assert payment.currency == "EUR"


def test_create_payment_duplicate_ok():
    service = PaymentService()
    idempotency_key = str(uuid.uuid4())

    for _ in range(2):
        payment_id = service.create_payment(idempotency_key, 10, "EUR")

        payment = service.get_payment(payment_id)
        assert payment.amount == 10
        assert payment.currency == "EUR"


@pytest.mark.parametrize(
    "idempotency_key, amount, currency,expected_exception",
    [
        (None, 10, "EUR", InvalidIdempotencyKey),
        ("invalid", 10, "EUR", InvalidIdempotencyKey),
        (2, 10, "EUR", InvalidIdempotencyKey),
        (str(uuid.uuid4()), -1, "EUR", InvalidAmount),
        (str(uuid.uuid4()), 0, "EUR", InvalidAmount),
        (str(uuid.uuid4()), "invalid", "EUR", InvalidAmount),
        (str(uuid.uuid4()), 10, 0, InvalidCurrency),
        (str(uuid.uuid4()), 10, "A", InvalidCurrency),
    ],
)
def test_create_payment_with_invalid_input(
    idempotency_key, amount, currency, expected_exception
):
    service = PaymentService()

    with pytest.raises(expected_exception):
        service.create_payment(idempotency_key, amount, currency)

def test_get_payment_not_found():
    service = PaymentService()
    
    with pytest.raises(PaymentNotFound):
        service.get_payment(str(uuid.uuid4()))
        
def test_create_account_amount_conflict():
    service = PaymentService()
    idempotency_key = str(uuid.uuid4())
    service.create_payment(idempotency_key, 10, "EUR")

    with pytest.raises(AmountOrCurrencyConflict):
        service.create_payment(idempotency_key, 9, "EUR")
def test_create_account_currency_conflict():
    service = PaymentService()
    idempotency_key = str(uuid.uuid4())
    service.create_payment(idempotency_key, 10, "EUR")

    with pytest.raises(AmountOrCurrencyConflict):
        service.create_payment(idempotency_key, 10, "AUSD")

def test_thread_safe_create_payment_duplicates():
    service = PaymentService()
    idempotency_key = str(uuid.uuid4())
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)

    def worker():
        barrier.wait()
        return service.create_payment(idempotency_key, 10, "EUR")

    with concurrent.futures.ThreadPoolExecutor(max_workers=number_of_threads) as executor:
        futures = [executor.submit(worker) for _ in range(number_of_threads)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    assert len(results) == number_of_threads
    assert results.count(results[0]) == number_of_threads

