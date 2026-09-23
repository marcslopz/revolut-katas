import copy
import dataclasses
import datetime
import threading
import uuid


class ValidationException(Exception):
    pass


class InvalidDiscount(ValidationException):
    pass


class InvalidMaxRedemptions(ValidationException):
    pass


class InvalidDuration(ValidationException):
    pass


class ServiceException(Exception):
    pass


class PromoCodeNotFound(ServiceException):
    pass


class MaxRedemptionsReached(ServiceException):
    pass


class UserAlreadyRedeem(ServiceException):
    pass


class ExpiredPromoCode(ServiceException):
    pass


@dataclasses.dataclass
class Promo:
    discount: int
    max_redemptions: int
    duration_in_days: int
    created_at: datetime.datetime
    users_with_redemption: set[uuid.UUID] = dataclasses.field(default_factory=set)
    promo_code: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)

    def __post_init__(self):
        if (
            not isinstance(self.discount, int)
            or self.discount <= 0
            or self.discount >= 100
        ):
            raise InvalidDiscount(self.discount)
        if not isinstance(self.max_redemptions, int) or self.max_redemptions <= 0:
            raise InvalidMaxRedemptions(self.max_redemptions)
        if not isinstance(self.duration_in_days, int) or self.duration_in_days <= 0:
            raise InvalidDuration(self.duration_in_days)

    def redeem(self, user_id: uuid.UUID, now: datetime.datetime) -> None:
        if len(self.users_with_redemption) == self.max_redemptions:
            raise MaxRedemptionsReached(self.promo_code)
        if user_id in self.users_with_redemption:
            raise UserAlreadyRedeem(self.promo_code, user_id)
        if self.created_at + datetime.timedelta(days=self.duration_in_days) < now:
            raise ExpiredPromoCode(self.promo_code, now)
        self.users_with_redemption.add(user_id)


class PromoRedemptionService:
    def __init__(self):
        self._promos: dict[uuid.UUID, Promo] = {}
        self._lock = threading.Lock()

    def create_promo_code(
        self,
        discount: int,
        max_redemptions: int,
        duration_in_days: int,
        now: datetime.datetime | None = None,
    ) -> uuid.UUID:
        if now is None:
            now = datetime.datetime.now()
        promo = Promo(discount, max_redemptions, duration_in_days, now)
        with self._lock:
            self._promos[promo.promo_code] = promo
            return promo.promo_code

    def redeem_promo_code(
        self,
        promo_code: uuid.UUID,
        user_id: uuid.UUID,
        now: datetime.datetime | None = None,
    ) -> None:
        if now is None:
            now = datetime.datetime.now()
        with self._lock:
            if promo_code not in self._promos:
                raise PromoCodeNotFound(promo_code)
            promo = self._promos[promo_code]
            promo.redeem(user_id, now)

    def get_promo_by_code(self, promo_code: uuid.UUID) -> Promo:
        with self._lock:
            if promo_code not in self._promos:
                raise PromoCodeNotFound(promo_code)
            return copy.copy(self._promos[promo_code])
