import pytest

from main import (
    CouponService,
    InvalidCouponCode,
    AlreadyExistingCouponCode,
    InvalidMaxRedemptions,
    CouponCodeNotFound,
    MaxRedemptionsReached,
)


def test_create_coupon_ok():
    service = CouponService()
    service.create_coupon("coupon_code_1", 10)

    assert service.get_coupon("coupon_code_1").code == "coupon_code_1"
    assert service.get_coupon("coupon_code_1").max_redemptions == 10


@pytest.mark.parametrize("coupon_code", [0, None, 0.1, True])
def test_create_coupon_invalid_code(coupon_code):
    service = CouponService()

    with pytest.raises(InvalidCouponCode):
        service.create_coupon(coupon_code, 10)


@pytest.mark.parametrize("max_redemptions", [0, -1, None, 0.1, True, "invalid"])
def test_create_coupon_invalid_max_redemptions(max_redemptions):
    service = CouponService()

    with pytest.raises(InvalidMaxRedemptions):
        service.create_coupon("coupon_code_1", max_redemptions)


def test_create_coupon_already_existing_coupon():
    service = CouponService()
    service.create_coupon("coupon_code_1", 10)

    with pytest.raises(AlreadyExistingCouponCode):
        service.create_coupon("coupon_code_1", 20)


def test_get_coupon_redemption_info_ok():
    service = CouponService()
    service.create_coupon("coupon_code_1", 10)
    service.redeem_coupon("coupon_code_1")
    service.redeem_coupon("coupon_code_1")

    response = service.get_coupon_redemption_info(coupon_code="coupon_code_1")

    assert response.number_of_redemptions == 2
    assert response.remaining_redemptions == 8


@pytest.mark.parametrize("coupon_code", [0, None, 0.1, True])
def test_get_coupon_redemption_info_invalid_code(coupon_code):
    service = CouponService()
    service.create_coupon("coupon_code_1", 10)

    with pytest.raises(InvalidCouponCode):
        service.get_coupon_redemption_info(coupon_code)


def test_redeem_coupon_ok():
    service = CouponService()
    service.create_coupon("coupon_code_1", 10)

    service.redeem_coupon("coupon_code_1")

    redemption_info = service.get_coupon_redemption_info(coupon_code="coupon_code_1")
    assert redemption_info.number_of_redemptions == 1
    assert redemption_info.remaining_redemptions == 9


@pytest.mark.parametrize("coupon_code", [0, None, 0.1, True])
def test_redeem_coupon_invalid_code(coupon_code):
    service = CouponService()

    with pytest.raises(InvalidCouponCode):
        service.redeem_coupon(coupon_code)


def test_redeem_coupon_not_found():
    service = CouponService()

    with pytest.raises(CouponCodeNotFound):
        service.redeem_coupon("coupon_code_1")


def test_redeem_coupon_max_redemptions_reached():
    service = CouponService()
    service.create_coupon("coupon_code_1", 1)
    service.redeem_coupon("coupon_code_1")

    with pytest.raises(MaxRedemptionsReached):
        service.redeem_coupon("coupon_code_1")
