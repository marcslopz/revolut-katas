import threading
from concurrent import futures

import pytest

from main import ClientQuotaService, InvalidClientId, InvalidQuota, ClientNotFound


def test_create_client_ok():
    service = ClientQuotaService()

    service.create_client("client_1", 10, 60)

    client = service.get_client("client_1")
    assert client.client_id == "client_1"
    assert client.quota == 10
    assert client.current_requests == []


@pytest.mark.parametrize(
    "client_id, quota, expected_exception",
    [
        (None, 10, InvalidClientId),
        (1, 10, InvalidClientId),
        ("", 10, InvalidClientId),
        ("client_1", 0, InvalidQuota),
        ("client_1", -1, InvalidQuota),
        ("client_1", "invalid", InvalidQuota),
        ("client_1", None, InvalidQuota),
    ],
)
def test_create_client_invalid_input(client_id, quota, expected_exception):
    service = ClientQuotaService()

    with pytest.raises(expected_exception):
        service.create_client(client_id, quota, 60)


def test_record_request_ok():
    service = ClientQuotaService()
    service.create_client("client_1", 10, 60)

    allowed = service.record_client_request("client_1")

    client = service.get_client("client_1")
    assert allowed is True
    assert client.client_id == "client_1"
    assert client.quota == 10
    assert len(client.current_requests) == 1


def test_record_request_client_not_found():
    service = ClientQuotaService()

    with pytest.raises(ClientNotFound):
        service.record_client_request("client_1")

def test_record_request_client_above_quota():
    service = ClientQuotaService()
    service.create_client("client_1", 1, 60)

    allowed = service.record_client_request("client_1")
    client = service.get_client("client_1")
    assert allowed is True
    assert len(client.current_requests) == 1

    allowed = service.record_client_request("client_1")
    client = service.get_client("client_1")
    assert allowed is False
    assert len(client.current_requests) == 1

def test_thread_safe_record_request():
    service = ClientQuotaService()
    service.create_client("client_1", 1, 60)
    number_of_threads = 10
    barrier = threading.Barrier(10)
    def worker():
        barrier.wait()
        return service.record_client_request("client_1")

    with futures.ThreadPoolExecutor(max_workers=number_of_threads) as executor:
        thread_futures = [executor.submit(worker) for _ in range(number_of_threads)]
        results = [future.result() for future in thread_futures]

    assert results.count(True) == 1
    assert results.count(False) == number_of_threads - 1