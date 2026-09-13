import threading
from dataclasses import dataclass, field


class InvalidCouponCode(Exception):
    pass


class InvalidMaxRedemptions(Exception):
    pass


class AlreadyExistingCouponCode(Exception):
    pass


class CouponCodeNotFound(Exception):
    pass

class MaxRedemptionsReached(Exception):
    pass


@dataclass
class RedemptionInfoResponse:
    number_of_redemptions: int
    remaining_redemptions: int


@dataclass
class Coupon:
    code: str
    max_redemptions: int
    current_redemptions: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def get_redemption_info(self) -> RedemptionInfoResponse:
        with self.lock:
            number_of_redemptions = self.current_redemptions
            remaining_redemptions = self.max_redemptions - self.current_redemptions
        return RedemptionInfoResponse(
            number_of_redemptions=number_of_redemptions,
            remaining_redemptions=remaining_redemptions,
        )

    def redeem(self):
        with self.lock:
            if self.current_redemptions >= self.max_redemptions:
                raise MaxRedemptionsReached
            self.current_redemptions += 1


def validate_coupon_code(coupon_code: str) -> None:
    if not isinstance(coupon_code, str):
        raise InvalidCouponCode(coupon_code)


def validate_max_redemptions(max_redemptions: int) -> None:
    if type(max_redemptions) is not int or max_redemptions <= 0:
        raise InvalidMaxRedemptions(max_redemptions)


class CouponService:
    def __init__(self):
        self._coupons: dict[str, Coupon] = {}
        self._coupons_lock = threading.Lock()

    def create_coupon(self, coupon_code: str, max_redemptions: int) -> None:
        validate_coupon_code(coupon_code)
        validate_max_redemptions(max_redemptions)
        with self._coupons_lock:
            if coupon_code in self._coupons:
                raise AlreadyExistingCouponCode(coupon_code)
            self._coupons[coupon_code] = Coupon(
                code=coupon_code, max_redemptions=max_redemptions
            )

    def get_coupon(self, coupon_code: str) -> Coupon:
        validate_coupon_code(coupon_code)
        with self._coupons_lock:
            if coupon_code not in self._coupons:
                raise CouponCodeNotFound(coupon_code)
            coupon = self._coupons[coupon_code]
        return coupon

    def get_coupon_redemption_info(self, coupon_code: str) -> RedemptionInfoResponse:
        validate_coupon_code(coupon_code)
        with self._coupons_lock:
            if coupon_code not in self._coupons:
                raise CouponCodeNotFound(coupon_code)
            coupon = self._coupons[coupon_code]
        return coupon.get_redemption_info()


    def redeem_coupon(self, coupon_code: str) -> None:
        validate_coupon_code(coupon_code)
        with self._coupons_lock:
            if coupon_code not in self._coupons:
                raise CouponCodeNotFound(coupon_code)
            coupon = self._coupons[coupon_code]
        coupon.redeem()
