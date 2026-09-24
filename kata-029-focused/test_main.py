import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from main import RegisterService, UsernameTaken, UsernameNotFound


class TestRegister:
    def setup_method(self) -> None:
        self.service = RegisterService()
        self.username = "user_1"

    def test_register_marks_username_as_taken(self) -> None:
        self.service.register(self.username)
        assert self.service.is_taken(self.username) is True

    def test_register_raises_when_already_taken(self) -> None:
        self.service.register(self.username)
        with pytest.raises(UsernameTaken):
            self.service.register(self.username)


class TestRelease:
    def setup_method(self) -> None:
        self.service = RegisterService()
        self.username = "user_1"
        self.service.register(self.username)

    def test_release_frees_username(self) -> None:
        self.service.release(self.username)
        assert self.service.is_taken(self.username) is False

    def test_release_raises_when_not_found(self) -> None:
        with pytest.raises(UsernameNotFound):
            self.service.release("not found")


class TestIsTaken:
    def setup_method(self) -> None:
        self.service = RegisterService()
        self.username = "user_1"

    def test_is_taken_false_when_unregistered(self) -> None:
        assert self.service.is_taken(self.username) is False

    def test_is_taken_true_when_registered(self) -> None:
        self.service.register(self.username)
        assert self.service.is_taken(self.username) is True

class TestConcurrency():
    def setup_method(self) -> None:
        self.service = RegisterService()
        self.num_of_threads = 10
        self.username = "user_1"

    def test_concurrent_register(self) -> None:
        barrier = threading.Barrier(self.num_of_threads)
        def try_register_user():
            barrier.wait()
            try:
                self.service.register(self.username)
                return True
            except UsernameTaken:
                return False
        with ThreadPoolExecutor(max_workers=self.num_of_threads) as executor:
            futures = [executor.submit(try_register_user) for _ in range(self.num_of_threads)]
            results = [future.result() for future in futures]

        assert len(results) == self.num_of_threads
        assert results.count(True) == 1
        assert results.count(False) == self.num_of_threads - 1
