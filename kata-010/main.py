import threading
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class SubscriptionStatus(StrEnum):
    active = "active"
    cancelled = "cancelled"


class ValidationException(Exception):
    pass


class InvalidId(ValidationException):
    pass


def get_uuid_from_str(uuid_str: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(uuid_str))
    except ValueError:
        raise InvalidId(uuid_str)


@dataclass(frozen=True)
class SubscriptionDto:
    user_id: str
    plan_id: str
    status: str
    subscription_id: str


@dataclass
class Subscription:
    user_id: uuid.UUID
    plan_id: uuid.UUID
    status: SubscriptionStatus = SubscriptionStatus.active
    lock: threading.Lock = field(default_factory=threading.Lock)
    subscription_id: uuid.UUID = field(default_factory=uuid.uuid4)

    def cancel(self):
        with self.lock:
            self.status = SubscriptionStatus.cancelled

    def to_dto(self) -> SubscriptionDto:
        with self.lock:
            return SubscriptionDto(
                str(self.user_id),
                str(self.plan_id),
                self.status,
                str(self.subscription_id),
            )


class ServiceException(Exception):
    pass


class SubscriptionNotFound(ServiceException):
    pass


class CancellationDenied(ServiceException):
    pass
class UserWithAlreadyActiveSubscription(ServiceException):
    pass


class SubscriptionService:
    def __init__(
        self,
    ) -> None:
        self._subscriptions: dict[uuid.UUID, Subscription] = {}
        self._user_active_subscriptions: dict[uuid.UUID, uuid.UUID] = {}
        self._lock: threading.Lock = threading.Lock()

    def create_subscription(self, user_id: str, plan_id: str) -> str:
        user_uuid = get_uuid_from_str(user_id)
        plan_uuid = get_uuid_from_str(plan_id)
        subscription = Subscription(user_uuid, plan_uuid)
        with self._lock:
            if user_uuid in self._user_active_subscriptions:
                raise UserWithAlreadyActiveSubscription(user_id)
            self._subscriptions[subscription.subscription_id] = subscription
            self._user_active_subscriptions[user_uuid] = subscription.subscription_id
        return str(subscription.subscription_id)

    def cancel_subscription(self, subscription_id: str, user_id: str) -> None:
        subscription_uuid = get_uuid_from_str(subscription_id)
        user_uuid = get_uuid_from_str(user_id)
        with self._lock:
            if subscription_uuid not in self._subscriptions:
                raise SubscriptionNotFound
            subscription = self._subscriptions[subscription_uuid]
            if user_uuid not in self._user_active_subscriptions:
                raise CancellationDenied
            user_subscription_uuid = self._user_active_subscriptions[user_uuid]
            user_subscription = self._subscriptions[user_subscription_uuid]
            if user_subscription.user_id != subscription.user_id:
                raise CancellationDenied
            del self._user_active_subscriptions[user_uuid]
        subscription.cancel()

    def get_subscription(self, subscription_id: str) -> SubscriptionDto:
        subscription_uuid = get_uuid_from_str(subscription_id)
        with self._lock:
            if subscription_uuid not in self._subscriptions:
                raise SubscriptionNotFound
            subscription = self._subscriptions[subscription_uuid]

        return subscription.to_dto()
