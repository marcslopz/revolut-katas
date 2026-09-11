import concurrent
import threading
from decimal import Decimal
from unittest import mock

import pytest

from main import (
    InvalidMerchantException,
    ChargeMerchantService,
    InvalidAmountException,
    MerchantNotFoundException,
    AccumulatedAmountExceededException,
    _quantize_amount,
    AlreadyExistingMerchantException,
    InvalidCapException,
    _charge_amount,
)


def test_none_merchant_should_raise_exception():
    charge_merchant_service = ChargeMerchantService({})
    with pytest.raises(InvalidMerchantException):
        charge_merchant_service.charge_merchant(None, Decimal(10.0))


def test_none_amount_should_raise_exception():
    charge_merchant_service = ChargeMerchantService({})
    with pytest.raises(InvalidAmountException):
        charge_merchant_service.charge_merchant("12345", None)


def test_negative_amount_should_raise_exception():
    charge_merchant_service = ChargeMerchantService({})
    with pytest.raises(InvalidAmountException):
        charge_merchant_service.charge_merchant("12345", Decimal(-1.0))


def test_not_found_merchant_should_raise_exception():
    charge_merchant_service = ChargeMerchantService({})
    with pytest.raises(MerchantNotFoundException):
        charge_merchant_service.charge_merchant("12345", Decimal(10.0))


def test_successful_first_charge():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)
    charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))

    charge_merchant_service.charge_merchant("merchant_1", Decimal(10.0))

    assert merchants_repository["merchant_1"]["charges"] == [Decimal(10.0)]
    assert merchants_repository["merchant_1"]["accumulated_charges"] == Decimal(10.0)
    assert merchants_repository["merchant_1"]["charges_cap"] == Decimal(20.0)


def test_successful_other_than_first_charge():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)
    charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))
    charge_merchant_service.charge_merchant("merchant_1", Decimal(10.0))

    charge_merchant_service.charge_merchant("merchant_1", Decimal(9.99))

    assert merchants_repository["merchant_1"]["charges"] == [
        Decimal(10.0),
        _quantize_amount(Decimal(9.99)),
    ]
    assert merchants_repository["merchant_1"][
        "accumulated_charges"
    ] == _quantize_amount(Decimal(19.99))
    assert merchants_repository["merchant_1"]["charges_cap"] == Decimal(20.0)


def test_first_charge_is_capped():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)
    charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))

    with pytest.raises(AccumulatedAmountExceededException):
        charge_merchant_service.charge_merchant("merchant_1", Decimal(20.1))


def test_other_than_first_charge_is_capped():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)
    charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))
    charge_merchant_service.charge_merchant("merchant_1", Decimal(10.0))

    with pytest.raises(AccumulatedAmountExceededException):
        charge_merchant_service.charge_merchant("merchant_1", Decimal(10.1))


def test_round_amount_half_down():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)
    charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))
    charge_merchant_service.charge_merchant("merchant_1", Decimal(10.0))

    charge_merchant_service.charge_merchant("merchant_1", Decimal(9.113))

    assert merchants_repository["merchant_1"]["charges"] == [
        Decimal(10.0),
        _quantize_amount(Decimal(9.11)),
    ]
    assert merchants_repository["merchant_1"][
        "accumulated_charges"
    ] == _quantize_amount(Decimal(19.11))
    assert merchants_repository["merchant_1"]["charges_cap"] == Decimal(20.0)


def test_round_amount_half_up():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)
    charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))
    charge_merchant_service.charge_merchant("merchant_1", Decimal(10.0))

    charge_merchant_service.charge_merchant("merchant_1", Decimal(9.115))

    assert merchants_repository["merchant_1"]["charges"] == [
        Decimal(10.0),
        _quantize_amount(Decimal(9.12)),
    ]
    assert merchants_repository["merchant_1"][
        "accumulated_charges"
    ] == _quantize_amount(Decimal(19.12))
    assert merchants_repository["merchant_1"]["charges_cap"] == _quantize_amount(
        Decimal(20.0)
    )


def test_register_null_merchant():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(InvalidMerchantException):
        charge_merchant_service.register_merchant(None, Decimal(20.0))


def test_register_null_cap():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(InvalidCapException):
        charge_merchant_service.register_merchant("merchant_1", None)


def test_register_invalid_merchant():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(InvalidMerchantException):
        charge_merchant_service.register_merchant(Decimal(1.0), Decimal(20.0))


def test_register_negative_cap():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(InvalidCapException):
        charge_merchant_service.register_merchant("merchant_1", Decimal(-20.0))


def test_register_zero_cap():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(InvalidCapException):
        charge_merchant_service.register_merchant("merchant_1", Decimal(0.0))


def test_register_invalid_type_cap():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(InvalidCapException):
        charge_merchant_service.register_merchant("merchant_1", "invalid_type")


def test_register_already_existing_merchant():
    merchants_repository = {"merchant_1": {}}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(AlreadyExistingMerchantException):
        charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))


def test_register_merchant_ok():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))

    assert merchants_repository["merchant_1"]["charges"] == []
    assert merchants_repository["merchant_1"][
        "accumulated_charges"
    ] == _quantize_amount(Decimal(0))
    assert merchants_repository["merchant_1"]["charges_cap"] == _quantize_amount(
        Decimal(20.0)
    )


def test_get_cap_merchant_not_found():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(MerchantNotFoundException):
        charge_merchant_service.get_cap_amount("merchant_1")


def test_get_cap_null_merchant():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(InvalidMerchantException):
        charge_merchant_service.get_cap_amount(None)


def test_get_cap_invalid_merchant():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)

    with pytest.raises(InvalidMerchantException):
        charge_merchant_service.get_cap_amount(Decimal(1.0))


def test_get_cap_ok():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)
    charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))
    charge_merchant_service.charge_merchant("merchant_1", Decimal(11.0))

    returned_quota_dict = charge_merchant_service.get_cap_amount("merchant_1")

    assert returned_quota_dict["cap"] == _quantize_amount(Decimal(20.0))
    assert returned_quota_dict["quota_left"] == _quantize_amount(Decimal(9.0))
    assert returned_quota_dict["accumulated_charges"] == _quantize_amount(Decimal(11.0))


def test_check_charge_amount_thread_safe():
    merchants_repository = {}
    charge_merchant_service = ChargeMerchantService(merchants_repository)
    charge_merchant_service.register_merchant("merchant_1", Decimal(20.0))
    barrier = threading.Barrier(3)

    def worker():
        barrier.wait()
        try:
            charge_merchant_service.charge_merchant("merchant_1", Decimal(11.0))
            return "success"
        except AccumulatedAmountExceededException:
            return "error"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        barrier.wait()
        results = [future.result() for future in futures]

    assert (results.count("success"), results.count("error")) == (1, 1)
