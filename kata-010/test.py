import concurrent.futures
import threading
import uuid

import pytest

from main import (
    SubscriptionService,
    SubscriptionStatus,
    InvalidId,
    CancellationDenied,
    SubscriptionNotFound,
    UserWithAlreadyActiveSubscription,
)


def test_create_subscription():
    service = SubscriptionService()
    user_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())

    subscription_id = service.create_subscription(user_id, plan_id)

    subscription_dto = service.get_subscription(subscription_id)
    assert subscription_dto.status == SubscriptionStatus.active
    assert subscription_dto.plan_id == plan_id
    assert subscription_dto.user_id == user_id
    assert subscription_dto.subscription_id == subscription_id


def test_create_two_subscriptions_for_the_same_user_id():
    service = SubscriptionService()
    user_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())

    _ = service.create_subscription(user_id, plan_id)
    with pytest.raises(UserWithAlreadyActiveSubscription):
        service.create_subscription(user_id, plan_id)

def test_cancel_subscription_should_allow_user_to_create_new_one():
    service = SubscriptionService()
    user_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())

    subscription_id = service.create_subscription(user_id, plan_id)
    service.cancel_subscription(subscription_id, user_id)
    new_subscription_id = service.create_subscription(user_id, plan_id)
    with pytest.raises(UserWithAlreadyActiveSubscription):
        service.create_subscription(user_id, plan_id)

    cancelled_subscription_dto = service.get_subscription(subscription_id)
    assert cancelled_subscription_dto.status == SubscriptionStatus.cancelled

    new_subscription_dto = service.get_subscription(new_subscription_id)
    assert new_subscription_dto.status == SubscriptionStatus.active


@pytest.mark.parametrize(
    "user_id, plan_id",
    [
        (None, str(uuid.uuid4())),
        ("invalid", str(uuid.uuid4())),
        (42, str(uuid.uuid4())),
        (str(uuid.uuid4()), None),
        (str(uuid.uuid4()), "invalid"),
        (str(uuid.uuid4()), 42),
    ],
)
def test_create_subscription_invalid_input(user_id, plan_id):
    service = SubscriptionService()

    with pytest.raises(InvalidId):
        # noinspection bad-argument-type
        service.create_subscription(user_id, plan_id)


def test_cancel_subscription():
    service = SubscriptionService()
    user_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    subscription_id = service.create_subscription(user_id, plan_id)

    service.cancel_subscription(subscription_id, user_id)

    subscription_dto = service.get_subscription(subscription_id)
    assert subscription_dto.status == SubscriptionStatus.cancelled


def test_cancel_subscription_different_user_id():
    service = SubscriptionService()
    user_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    subscription_id = service.create_subscription(user_id, plan_id)

    with pytest.raises(CancellationDenied):
        service.cancel_subscription(subscription_id, str(uuid.uuid4()))

    subscription_dto = service.get_subscription(subscription_id)
    assert subscription_dto.status == SubscriptionStatus.active


def test_cancel_subscription_not_found():
    service = SubscriptionService()
    user_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    subscription_id = service.create_subscription(user_id, plan_id)

    with pytest.raises(SubscriptionNotFound):
        service.cancel_subscription(str(uuid.uuid4()), user_id)

    subscription_dto = service.get_subscription(subscription_id)
    assert subscription_dto.status == SubscriptionStatus.active


@pytest.mark.parametrize(
    "subscription_id, user_id",
    [
        (None, str(uuid.uuid4())),
        ("invalid", str(uuid.uuid4())),
        (42, str(uuid.uuid4())),
        (str(uuid.uuid4()), None),
        (str(uuid.uuid4()), "invalid"),
        (str(uuid.uuid4()), 42),
    ],
)
def test_cancel_subscription_invalid_input(subscription_id, user_id):
    service = SubscriptionService()

    with pytest.raises(InvalidId):
        # noinspection bad-argument-type
        service.cancel_subscription(subscription_id, user_id)


def test_get_subscription():
    service = SubscriptionService()
    user_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    subscription_id = service.create_subscription(user_id, plan_id)

    subscription_dto = service.get_subscription(subscription_id)

    assert subscription_dto.status == SubscriptionStatus.active
    assert subscription_dto.plan_id == plan_id
    assert subscription_dto.user_id == user_id
    assert subscription_dto.subscription_id == subscription_id


@pytest.mark.parametrize(
    "subscription_id",
    [
        None,
        "invalid",
        42,
    ],
)
def test_get_subscription_invalid_input(subscription_id):
    service = SubscriptionService()

    with pytest.raises(InvalidId):
        # noinspection bad-argument-type
        service.get_subscription(subscription_id)


def test_concurrent_create_subscription():
    service = SubscriptionService()
    user_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    barrier = threading.Barrier(2)
    def worker():
        barrier.wait()
        try:
            return service.create_subscription(user_id, plan_id)
        except UserWithAlreadyActiveSubscription:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        results = [future.result() for future in futures]

    assert len(results) == 2
    assert results.count(None) == 1
    subscription_id = [result for result in results if result is not None][0]
    dto = service.get_subscription(subscription_id)
    assert dto.status == SubscriptionStatus.active

def test_concurrent_create_and_cancel():
    service = SubscriptionService()
    user_id = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    subscription_id = service.create_subscription(user_id, plan_id)
    barrier = threading.Barrier(2)
    def worker_cancel():
        barrier.wait()
        # noinspection broad-exception
        try:
            service.cancel_subscription(subscription_id, user_id)
            return True
        except Exception:
            return False

    def worker_create():
        barrier.wait()
        try:
            return service.create_subscription(user_id, plan_id)
        except UserWithAlreadyActiveSubscription:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_cancel = executor.submit(worker_cancel)
        future_create = executor.submit(worker_create)
        result_cancel = future_cancel.result()
        result_create = future_create.result()

    assert result_cancel is True
    dto = service.get_subscription(subscription_id)
    assert dto.status == SubscriptionStatus.cancelled
    if result_create is not None:
        dto_new = service.get_subscription(result_create)
        assert dto_new.status == SubscriptionStatus.active