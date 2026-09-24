import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from main import ParkingService, SpotNotAvailable, ExceedCapacity


class TestEnter:
    def setup_method(self) -> None:
        self.service = ParkingService(capacity=1)

    def test_enter_occupies_a_spot(self) -> None:
        self.service.enter()
        assert self.service._spots == 0

    def test_enter_raises_when_full(self) -> None:
        self.service.enter()
        with pytest.raises(SpotNotAvailable):
            self.service.enter()

class TestExit:
    def setup_method(self) -> None:
        self.service = ParkingService(capacity=1)
        self.service.enter()
        assert self.service.available_spots() == 0

    def test_exit_frees_a_spot(self) -> None:
        self.service.exit()
        assert self.service._spots == 1

    def test_exit_does_not_exceed_capacity(self) -> None:
        self.service.exit()
        with pytest.raises(ExceedCapacity):
            self.service.exit()


class TestAvailableSpots:
    def setup_method(self) -> None:
        self.service = ParkingService(capacity=2)

    def test_available_spots_reflects_capacity(self) -> None:
        spots = self.service.available_spots()
        assert spots == 2


    def test_available_spots_decreases_on_enter(self) -> None:
        self.service.enter()
        assert self.service.available_spots() == 1

    def test_available_spots_increases_on_exit(self) -> None:
        self.service.enter()
        assert self.service.available_spots() == 1

        self.service.exit()
        assert self.service.available_spots() == 2


class TestConcurrency:
    def setup_method(self) -> None:
        self.service = ParkingService(capacity=4)

    def test_only_capacity_vehicles_enter_under_concurrency(self) -> None:
        n_threads = 10
        barrier = threading.Barrier(n_threads)

        def try_enter(_) -> bool:
            barrier.wait()
            try:
                self.service.enter()
                return True
            except SpotNotAvailable:
                return False

        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            results = list(executor.map(try_enter, range(n_threads)))

        assert results.count(True) == 4
        assert results.count(False) == 6
        assert self.service.available_spots() == 0

