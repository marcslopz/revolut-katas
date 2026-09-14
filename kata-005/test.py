import pytest

from main import ClientQuotaService, InvalidClientId, InvalidQuota, ClientNotFound


def test_create_client_ok():
    service = ClientQuotaService()

    service.create_client("client_1", 10)

    client = service.get_client("client_1")
    assert client.client_id == "client_1"
    assert client.quota == 10
    assert client.current_requests == 0


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
        service.create_client(client_id, quota)


def test_record_request_ok():
    service = ClientQuotaService()
    service.create_client("client_1", 10)

    service.record_client_request("client_1")

    client = service.get_client("client_1")
    assert client.client_id == "client_1"
    assert client.quota == 10
    assert client.current_requests == 1


def test_record_request_client_not_found():
    service = ClientQuotaService()

    with pytest.raises(ClientNotFound):
        service.record_client_request("client_1")

