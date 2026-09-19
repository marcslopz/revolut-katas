import concurrent.futures
import threading
import uuid

import pytest

from main import (
    AccountService,
    InvalidBalance,
    InvalidUuid,
    InvalidPoints,
    AccountNotFound,
    NotEnoughPoints,
    OperationType,
    OperationDto,
)


def test_create_account():
    service = AccountService()

    account_id = service.create_account(0)

    assert service.get_balance(account_id) == 0
    uuid.UUID(str(account_id))


@pytest.mark.parametrize("initial_balance", ["invalid", None, -1])
def test_create_account_invalid_input(initial_balance):
    service = AccountService()

    with pytest.raises(InvalidBalance):
        # noinspection bad-argument-type
        service.create_account(initial_balance)


def test_earn_points():
    service = AccountService()
    account_id = service.create_account(0)

    service.earn_points(account_id, 1)

    assert service.get_balance(account_id) == 1


@pytest.mark.parametrize(
    "account_id, points, expected_exception",
    [
        (None, 1, InvalidUuid),
        (1, 1, InvalidUuid),
        ("invalid", 1, InvalidUuid),
        (str(uuid.uuid4()), 0, InvalidPoints),
        (str(uuid.uuid4()), -1, InvalidPoints),
        (str(uuid.uuid4()), "invalid", InvalidPoints),
        (str(uuid.uuid4()), None, InvalidPoints),
    ],
)
def test_earn_points_invalid_input(account_id, points, expected_exception):
    service = AccountService()
    _ = service.create_account(0)

    with pytest.raises(expected_exception):
        # noinspection bad-argument-type
        service.earn_points(account_id, points)


def test_redeem_points():
    service = AccountService()
    account_id = service.create_account(1)

    service.redeem_points(account_id, 1)

    assert service.get_balance(account_id) == 0


@pytest.mark.parametrize(
    "account_id, points, expected_exception",
    [
        (None, 1, InvalidUuid),
        (1, 1, InvalidUuid),
        ("invalid", 1, InvalidUuid),
        (str(uuid.uuid4()), 0, InvalidPoints),
        (str(uuid.uuid4()), -1, InvalidPoints),
        (str(uuid.uuid4()), "invalid", InvalidPoints),
        (str(uuid.uuid4()), None, InvalidPoints),
    ],
)
def test_redeem_points_invalid_input(account_id, points, expected_exception):
    service = AccountService()
    _ = service.create_account(0)

    with pytest.raises(expected_exception):
        # noinspection bad-argument-type
        service.redeem_points(account_id, points)


def test_earn_points_account_not_found():
    service = AccountService()

    with pytest.raises(AccountNotFound):
        service.earn_points(str(uuid.uuid4()), 1)


def test_redeem_points_account_not_found():
    service = AccountService()

    with pytest.raises(AccountNotFound):
        service.redeem_points(str(uuid.uuid4()), 1)


def test_redeem_points_not_enough_points():
    service = AccountService()
    account_id = service.create_account(0)

    with pytest.raises(NotEnoughPoints):
        service.redeem_points(account_id, 1)


def test_get_account_operations_empty():
    service = AccountService()
    account_id = service.create_account(0)

    operations = service.get_account_operations(account_id)

    assert len(operations) == 0


def test_get_account_operations():
    service = AccountService()
    account_id = service.create_account(0)

    service.earn_points(account_id, 2)
    service.redeem_points(account_id, 1)

    operations = service.get_account_operations(account_id)

    assert len(operations) == 2
    assert operations[0].points == 2
    assert operations[1].points == 1
    assert operations[0].type == OperationType.EARN
    assert operations[1].type == OperationType.REDEEM


def test_get_account_operations_account_not_found():
    service = AccountService()
    with pytest.raises(AccountNotFound):
        service.get_account_operations(str(uuid.uuid4()))


@pytest.mark.parametrize("account_id", ["invalid", None, 1])
def test_get_account_operations_invalid_input(account_id):
    service = AccountService()

    with pytest.raises(InvalidUuid):
        # noinspection bad-argument-type
        service.get_account_operations(account_id)


def test_transfer_points():
    service = AccountService()
    from_account_id = service.create_account(1)
    to_account_id = service.create_account(0)

    service.transfer_points(from_account_id, to_account_id, 1)

    assert service.get_balance(from_account_id) == 0
    assert service.get_balance(to_account_id) == 1
    to_account_operations_dto = service.get_account_operations(to_account_id)
    from_account_operations_dto = service.get_account_operations(from_account_id)
    assert len(from_account_operations_dto) == 1
    assert len(to_account_operations_dto) == 1
    assert from_account_operations_dto[0] == OperationDto(
        OperationType.TRANSFER_TO.value, 1, to_account_id
    )
    assert to_account_operations_dto[0] == OperationDto(
        OperationType.TRANSFER_FROM.value, 1, from_account_id
    )


def test_transfer_points_from_account_not_found():
    service = AccountService()
    to_account_id = service.create_account(0)

    with pytest.raises(AccountNotFound):
        service.transfer_points(str(uuid.uuid4()), to_account_id, 1)


def test_transfer_points_to_account_not_found():
    service = AccountService()
    from_account_id = service.create_account(0)

    with pytest.raises(AccountNotFound):
        service.transfer_points(from_account_id, str(uuid.uuid4()), 1)


def test_transfer_points_not_enough_points():
    service = AccountService()
    from_account_id = service.create_account(0)
    to_account_id = service.create_account(1)
    with pytest.raises(NotEnoughPoints):
        service.transfer_points(from_account_id, to_account_id, 1)


@pytest.mark.parametrize(
    "from_account_id, to_account_id, points, expected_exception",
    [
        (None, str(uuid.uuid4()), 1, InvalidUuid),
        ("invalid", str(uuid.uuid4()), 1, InvalidUuid),
        (0, str(uuid.uuid4()), 1, InvalidUuid),
        (str(uuid.uuid4()), None, 1, InvalidUuid),
        (str(uuid.uuid4()), "invalid", 1, InvalidUuid),
        (str(uuid.uuid4()), 0, 1, InvalidUuid),
        (str(uuid.uuid4()), str(uuid.uuid4()), 0, InvalidPoints),
        (str(uuid.uuid4()), str(uuid.uuid4()), -1, InvalidPoints),
        (str(uuid.uuid4()), str(uuid.uuid4()), "invalid", InvalidPoints),
        (str(uuid.uuid4()), str(uuid.uuid4()), None, InvalidPoints),
    ],
)
def test_transfer_points_invalid_input(
    from_account_id, to_account_id, points, expected_exception
):
    service = AccountService()
    with pytest.raises(expected_exception):
        # noinspection bad-argument-type
        service.transfer_points(from_account_id, to_account_id, points)


def test_concurrent_redeem_points():
    service = AccountService()
    account_id = service.create_account(1)
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        try:
            service.redeem_points(account_id, 1)
            return True
        except NotEnoughPoints:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        results = [future.result() for future in futures]

    assert len(results) == 2
    assert results.count(True) == 1
    assert results.count(False) == 1
    operations = service.get_account_operations(account_id)
    assert len(operations) == 1
    assert operations[0] == OperationDto(OperationType.REDEEM, 1, None)

def test_concurrent_earn_points():
    service = AccountService()
    account_id = service.create_account(0)
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)

    def worker():
        barrier.wait()
        service.earn_points(account_id, 1)

    with concurrent.futures.ThreadPoolExecutor(max_workers=number_of_threads) as executor:
        futures = [executor.submit(worker) for _ in range(number_of_threads)]
        _ = [future.result() for future in futures]

    operations = service.get_account_operations(account_id)
    assert len(operations) == 10
    for operation in operations:
        assert operation == OperationDto(OperationType.EARN, 1, None)
    assert service.get_balance(account_id) == 10

def test_concurrent_transfer_points():
    service = AccountService()
    to_account_id = service.create_account(0)
    from_account_id = service.create_account(5)
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)

    def worker():
        barrier.wait()
        try:
            service.transfer_points(from_account_id, to_account_id, 1)
            return True
        except NotEnoughPoints:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=number_of_threads) as executor:
        futures = [executor.submit(worker) for _ in range(number_of_threads)]
        results = [future.result() for future in futures]

    assert len(results) == 10
    assert results.count(True) == 5
    assert results.count(False) == 5
    operations = service.get_account_operations(to_account_id)
    assert len(operations) == 5
    for operation in operations:
        assert operation == OperationDto(OperationType.TRANSFER_FROM, 1, from_account_id)
    assert service.get_balance(to_account_id) == 5
    operations = service.get_account_operations(from_account_id)
    assert len(operations) == 5
    for operation in operations:
        assert operation == OperationDto(OperationType.TRANSFER_TO, 1, to_account_id)
    assert service.get_balance(from_account_id) == 0

