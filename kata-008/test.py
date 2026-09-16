import concurrent.futures
import threading
import uuid

import pytest

from main import AccountService, NotEnoughBalance, AccountNotFound, IdempotencyConflict


def test_create_account():
    service = AccountService()

    account_id = service.create_account("user_1", 10)

    assert service.get_account_balance(account_id) == 10


def test_create_account_with_zero_balance():
    service = AccountService()

    account_id = service.create_account("user_1", 0)

    assert service.get_account_balance(account_id) == 0


@pytest.mark.parametrize(
    "user_id, balance",
    [
        ("", 10),
        (0, 10),
        ("user_1", -1),
        ("user_1", "invalid"),
    ],
)
def test_create_account_with_invalid_input(user_id, balance):
    service = AccountService()

    with pytest.raises(ValueError):
        account_id = service.create_account("user_1", -1)


def test_deposit_amount():
    service = AccountService()
    account_id = service.create_account("user_1", 10)

    service.deposit_amount(account_id, 10)

    assert service.get_account_balance(account_id) == 20


def test_withdraw_amount():
    service = AccountService()
    account_id = service.create_account("user_1", 10)

    service.withdraw_amount(account_id, 10)

    assert service.get_account_balance(account_id) == 0


def test_withdraw_amount():
    service = AccountService()
    account_id = service.create_account("user_1", 10)

    with pytest.raises(NotEnoughBalance):
        service.withdraw_amount(account_id, 20)

    assert service.get_account_balance(account_id) == 10


def test_transfer_amount():
    service = AccountService()
    account_id = service.create_account("user_1", 10)
    account_id2 = service.create_account("user_2", 10)

    service.transfer_amount("idem_1", account_id, account_id2, 10)

    assert service.get_account_balance(account_id) == 0
    assert service.get_account_balance(account_id2) == 20


def test_transfer_amount_not_enough_balance():
    service = AccountService()
    account_id = service.create_account("user_1", 10)
    account_id2 = service.create_account("user_2", 10)

    with pytest.raises(NotEnoughBalance):
        service.transfer_amount("idem_1", account_id, account_id2, 11)

    assert service.get_account_balance(account_id) == 10
    assert service.get_account_balance(account_id2) == 10


def test_transfer_account_not_found():
    service = AccountService()

    with pytest.raises(AccountNotFound):
        service.transfer_amount("idem_1", str(uuid.uuid4()), str(uuid.uuid4()), 10)


def test_concurrent_transfers():
    service = AccountService()
    account_id = service.create_account("user_1", 40)
    account_id2 = service.create_account("user_2", 10)
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)

    def worker():
        barrier.wait()
        try:
            service.transfer_amount(str(uuid.uuid4()), account_id, account_id2, 10)
            return True
        except NotEnoughBalance:
            return False

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=number_of_threads
    ) as executor:
        futures = [executor.submit(worker) for _ in range(number_of_threads)]
        results = [future.result() for future in futures]

    assert len(results) == number_of_threads
    assert results.count(True) == 4
    assert results.count(False) == number_of_threads - 4

def test_transfer_amount_idempotent():
    service = AccountService()
    account_id = service.create_account("user_1", 10)
    account_id2 = service.create_account("user_2", 10)

    service.transfer_amount("idem_1", account_id, account_id2, 10)
    service.transfer_amount("idem_1", account_id, account_id2, 10)

    assert service.get_account_balance(account_id) == 0
    assert service.get_account_balance(account_id2) == 20
def test_transfer_amount_idempotent_unmatching():
    service = AccountService()
    account_id = service.create_account("user_1", 10)
    account_id2 = service.create_account("user_2", 10)

    service.transfer_amount("idem_1", account_id, account_id2, 10)
    
    with pytest.raises(IdempotencyConflict):
        service.transfer_amount("idem_1", account_id, account_id2, 1)

    assert service.get_account_balance(account_id) == 0
    assert service.get_account_balance(account_id2) == 20
