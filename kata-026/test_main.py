import concurrent.futures
import datetime
import threading

import pytest

from main import (
    ReservationSeatService,
    SeatStatus,
    ReservationStatus,
    EmptySeatSet,
    SeatAlreadyHeld,
    ReservationAlreadyReleased,
    WrongCustomerIdForRelease,
    TTL_IN_SECONDS,
)


class TestHoldSeats:
    def setup_method(self):
        self.service = ReservationSeatService(
            {"1a", "1b", "1c", "1d", "1e", "2a", "2b", "2c", "2d", "2e"}
        )

    def test_hold_one_seat_ok(self):
        reservation_id = self.service.hold_seats("customer_1", {"1c"})

        assert self.service.get_seat_status("1c") == SeatStatus.HELD
        assert (
            self.service.get_reservation_status(reservation_id)
            == ReservationStatus.LOCKED
        )

    def test_hold_more_than_one_seat_ok(self):
        reservation_id = self.service.hold_seats("customer_1", {"1c", "1a"})

        assert self.service.get_seat_status("1c") == SeatStatus.HELD
        assert self.service.get_seat_status("1a") == SeatStatus.HELD
        assert (
            self.service.get_reservation_status(reservation_id)
            == ReservationStatus.LOCKED
        )

    def test_hold_zero_seats_error(self):
        with pytest.raises(EmptySeatSet):
            self.service.hold_seats("customer_1", set())

    def test_one_seat_already_held(self):
        _ = self.service.hold_seats("customer_1", {"1c"})

        with pytest.raises(SeatAlreadyHeld):
            self.service.hold_seats("customer_1", {"1a", "1c"})

    def test_check_seat_is_released_after_ttl(self):
        now = datetime.datetime.now()
        _ = self.service.hold_seats("customer_1", {"1c"})

        assert self.service.get_seat_status("1c", now) == SeatStatus.HELD
        after_ttl = now + datetime.timedelta(seconds=TTL_IN_SECONDS + 1)
        assert self.service.get_seat_status("1c", after_ttl) == SeatStatus.FREE

        reservation_id_2 = self.service.hold_seats("customer_2", {"1c"}, after_ttl)
        assert (
            self.service.get_reservation_status(reservation_id_2, after_ttl)
            == ReservationStatus.LOCKED
        )
        assert self.service.get_seat_status("1c", after_ttl) == SeatStatus.HELD


class TestReleaseReservation:
    def setup_method(self):
        self.service = ReservationSeatService({"1a", "1b"})

    def test_release_one_seat(self):
        reservation_id = self.service.hold_seats("customer_1", {"1a"})

        self.service.release_reservation("customer_1", reservation_id)

        assert (
            self.service.get_reservation_status(reservation_id)
            == ReservationStatus.RELEASED
        )
        assert self.service.get_seat_status("1a") == SeatStatus.FREE

    def test_release_duplicated_error(self):
        reservation_id = self.service.hold_seats("customer_1", {"1a"})
        self.service.release_reservation("customer_1", reservation_id)

        with pytest.raises(ReservationAlreadyReleased):
            self.service.release_reservation("customer_1", reservation_id)

    def test_release_from_mismatching_customer(self):
        reservation_id = self.service.hold_seats("customer_1", {"1a"})

        with pytest.raises(WrongCustomerIdForRelease):
            self.service.release_reservation("customer_2", reservation_id)

    def test_reservation_released_after_ttl(self):
        now = datetime.datetime.now()
        reservation_id = self.service.hold_seats("customer_1", {"1a"}, now)

        assert (
            self.service.get_reservation_status(reservation_id, now)
            == ReservationStatus.LOCKED
        )
        after_ttl = now + datetime.timedelta(seconds=TTL_IN_SECONDS + 1)
        assert (
            self.service.get_reservation_status(reservation_id, after_ttl)
            == ReservationStatus.RELEASED
        )


class TestConcurrency:
    def setup_method(self):
        self._seat_ids = {"0", "1", "2", "3", "4", "5"}
        self.service = ReservationSeatService(self._seat_ids)
        self.number_of_threads = 10

    def test_concurrent_holds(self):
        barrier = threading.Barrier(self.number_of_threads)

        def worker(seat_id: int):
            barrier.wait()
            try:
                self.service.hold_seats(
                    "customer_1", {str(seat_id % len(self._seat_ids))}
                )
                return True
            except SeatAlreadyHeld:
                return False

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.number_of_threads
        ) as executor:
            futures = [
                executor.submit(worker, seat_id)
                for seat_id in range(self.number_of_threads)
            ]
            results = [future.result() for future in futures]

        assert len(results) == self.number_of_threads
        assert results.count(True) == 6
        assert results.count(False) == self.number_of_threads - 6
