import concurrent.futures
import threading
import uuid

import pytest

from main import (
    WalletService,
    InvalidUserId,
    InvalidInitialBalance,
    InvalidWalletId,
    InvalidAmount,
    WalletNotFound,
    NotEnoughBalance,
)


def test_create_wallet_ok():
    service = WalletService()

    wallet_id = service.create_wallet("user_1", 10)

    wallet = service.get_wallet(wallet_id)
    assert wallet.balance == 10
    assert wallet.user_id == "user_1"


@pytest.mark.parametrize(
    "user_id, initial_balance, expected_exception",
    [
        (None, 10, InvalidUserId),
        (1, 10, InvalidUserId),
        ("user_1", None, InvalidInitialBalance),
        ("user_1", -1, InvalidInitialBalance),
    ],
)
def test_create_wallet_invalid_input(user_id, initial_balance, expected_exception):
    service = WalletService()

    with pytest.raises(expected_exception):
        service.create_wallet(user_id, initial_balance)


def test_deposit_funds_ok():
    service = WalletService()
    wallet_id = service.create_wallet("user_1", 10)

    service.deposit_funds(wallet_id, 1)

    wallet_dto = service.get_wallet(wallet_id)
    assert wallet_dto.balance == 11


@pytest.mark.parametrize(
    "wallet_id, amount, expected_exception",
    [
        (None, 10, InvalidWalletId),
        ("wrong", 10, InvalidWalletId),
        (1, 10, InvalidWalletId),
        (str(uuid.uuid4()), None, InvalidAmount),
        (str(uuid.uuid4()), -1, InvalidAmount),
        (str(uuid.uuid4()), 0, InvalidAmount),
    ],
)
def test_deposit_funds_invalid_input(wallet_id, amount, expected_exception):
    service = WalletService()

    with pytest.raises(expected_exception):
        service.deposit_funds(wallet_id, amount)


def test_deposit_funds_to_non_existing_wallet():
    service = WalletService()
    wallet_id = str(uuid.uuid4())

    with pytest.raises(WalletNotFound):
        service.deposit_funds(wallet_id, 1)


def test_withdraw_funds_ok():
    service = WalletService()
    wallet_id = service.create_wallet("user_1", 10)

    service.withdraw_funds(wallet_id, 1)

    wallet_dto = service.get_wallet(wallet_id)
    assert wallet_dto.balance == 9


@pytest.mark.parametrize(
    "wallet_id, amount, expected_exception",
    [
        (None, 10, InvalidWalletId),
        ("wrong", 10, InvalidWalletId),
        (1, 10, InvalidWalletId),
        (str(uuid.uuid4()), None, InvalidAmount),
        (str(uuid.uuid4()), -1, InvalidAmount),
        (str(uuid.uuid4()), 0, InvalidAmount),
    ],
)
def test_withdraw_funds_invalid_input(wallet_id, amount, expected_exception):
    service = WalletService()

    with pytest.raises(expected_exception):
        service.withdraw_funds(wallet_id, amount)


def test_withdraw_funds_to_non_existing_wallet():
    service = WalletService()
    wallet_id = str(uuid.uuid4())

    with pytest.raises(WalletNotFound):
        service.withdraw_funds(wallet_id, 1)


def test_withdraw_funds_exceeding_the_current_balance():
    service = WalletService()
    wallet_id = service.create_wallet("user_1", 10)

    with pytest.raises(NotEnoughBalance):
        service.withdraw_funds(wallet_id, 11)


def test_get_balance_ok():
    service = WalletService()
    wallet_id = service.create_wallet("user_1", 10)

    balance = service.get_balance(wallet_id)

    assert balance == 10


@pytest.mark.parametrize(
    "wallet_id, expected_exception",
    [
        (None, InvalidWalletId),
        ("wrong", InvalidWalletId),
        (1, InvalidWalletId),
    ],
)
def test_get_balance_invalid_input(wallet_id, expected_exception):
    service = WalletService()

    with pytest.raises(expected_exception):
        service.get_balance(wallet_id)


def test_get_balance_from_non_existing_wallet():
    service = WalletService()
    wallet_id = str(uuid.uuid4())

    with pytest.raises(WalletNotFound):
        service.get_balance(wallet_id)


def test_transfer_funds_ok():
    service = WalletService()
    wallet_id_src = service.create_wallet("user_1", 10)
    wallet_id_dst = service.create_wallet("user_2", 5)

    service.transfer_funds(wallet_id_src, wallet_id_dst, 3, str(uuid.uuid4()))

    wallet_src_dto = service.get_wallet(wallet_id_src)
    wallet_dst_dto = service.get_wallet(wallet_id_dst)

    assert wallet_src_dto.balance == 7
    assert wallet_dst_dto.balance == 8


def test_thread_safe_transfers_with_idempotency_key():
    service = WalletService()
    wallet_id_src = service.create_wallet("user_1", 10)
    wallet_id_dst = service.create_wallet("user_2", 5)

    numbert_of_threads = 10
    barrier = threading.Barrier(numbert_of_threads)
    idempotency_key = str(uuid.uuid4())

    def worker():
        barrier.wait()
        try:
            service.transfer_funds(wallet_id_src, wallet_id_dst, 3, idempotency_key)
            return True
        except Exception:
            return False

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(worker) for _ in range(numbert_of_threads)]
        results = [future.result() for future in futures]

    assert all(results) is True
    wallet_src_dto = service.get_wallet(wallet_id_src)
    wallet_dst_dto = service.get_wallet(wallet_id_dst)
    assert wallet_src_dto.balance == 7
    assert wallet_dst_dto.balance == 8
