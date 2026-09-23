import concurrent.futures
import datetime
import threading
import uuid

import pytest

from main import (
    PromoRedemptionService,
    PromoCodeNotFound,
    MaxRedemptionsReached,
    UserAlreadyRedeem,
    ExpiredPromoCode,
)


class TestCreatePromoCode:
    def setup_method(self):
        self.service = PromoRedemptionService()

    def test_create_promo_code_ok(self):
        promo_code = self.service.create_promo_code(5, 10, 1)

        promo = self.service.get_promo_by_code(promo_code)
        assert promo.discount == 5
        assert promo.promo_code == promo_code
        assert promo.max_redemptions == 10
        assert len(promo.users_with_redemption) == 0


class TestRedeemPromoCode:
    def setup_method(self):
        self.service = PromoRedemptionService()
        self.now = datetime.datetime.now()
        self.duration_in_days = 1
        self.promo_code = self.service.create_promo_code(
            5, 2, self.duration_in_days, self.now
        )
        self.user_1_id = uuid.uuid4()
        self.user_2_id = uuid.uuid4()
        self.user_3_id = uuid.uuid4()

    def test_redeem_promo_code_ok(self):
        self.service.redeem_promo_code(self.promo_code, self.user_1_id)

        promo = self.service.get_promo_by_code(self.promo_code)
        assert len(promo.users_with_redemption) == 1

    def test_redeem_promo_code_not_found(self):
        with pytest.raises(PromoCodeNotFound):
            self.service.redeem_promo_code(uuid.uuid4(), self.user_2_id)

    def test_redeem_promo_code_max_redemptions_reached(self):
        self.service.redeem_promo_code(self.promo_code, self.user_1_id)
        self.service.redeem_promo_code(self.promo_code, self.user_2_id)

        with pytest.raises(MaxRedemptionsReached):
            self.service.redeem_promo_code(self.promo_code, self.user_3_id)

        promo = self.service.get_promo_by_code(self.promo_code)
        assert len(promo.users_with_redemption) == 2

    def test_redeem_promo_code_already_redeemed_by_user(self):
        self.service.redeem_promo_code(self.promo_code, self.user_1_id)

        with pytest.raises(UserAlreadyRedeem):
            self.service.redeem_promo_code(self.promo_code, self.user_1_id)

        promo = self.service.get_promo_by_code(self.promo_code)
        assert len(promo.users_with_redemption) == 1

    def test_redeem_promo_code_expired(self):
        with pytest.raises(ExpiredPromoCode):
            self.service.redeem_promo_code(
                self.promo_code,
                self.user_1_id,
                self.now + datetime.timedelta(days=self.duration_in_days, seconds=1),
            )

        promo = self.service.get_promo_by_code(self.promo_code)
        assert len(promo.users_with_redemption) == 0

class TestConcurrency:
    def setup_method(self):
        self.service = PromoRedemptionService()
        self.number_of_threads = 10
        self.user_ids = [uuid.uuid4() for _ in range(self.number_of_threads)]
        self.max_redemptions = 6
        self.promo_code = self.service.create_promo_code(5, self.max_redemptions, 1)

    def test_concurrency_redemptions(self):
        barrier = threading.Barrier(self.number_of_threads)
        def worker(user_index):
            barrier.wait()
            try:
                self.service.redeem_promo_code(self.promo_code, self.user_ids[user_index])
                return True
            except MaxRedemptionsReached:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.number_of_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(self.number_of_threads)]
            results = [future.result() for future in futures]

        assert len(results) == self.number_of_threads
        assert results.count(True) == self.max_redemptions
        assert results.count(False) == self.number_of_threads - self.max_redemptions

