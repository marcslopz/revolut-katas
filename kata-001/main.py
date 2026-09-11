import threading
from decimal import Decimal


class InvalidMerchantException(Exception):
    pass


class InvalidAmountException(Exception):
    pass


class MerchantNotFoundException(Exception):
    pass


class AccumulatedAmountExceededException(Exception):
    pass


class AlreadyExistingMerchantException(Exception):
    pass


class InvalidCapException(Exception):
    pass


def _charge_amount(merchant, amount) -> None:
    merchant["charges"].append(amount)
    merchant["accumulated_charges"] = _quantize_amount(
        merchant["accumulated_charges"] + amount
    )


def _is_amount_exceeded(merchant, amount) -> bool:
    cap = merchant["charges_cap"]
    accumulated_amount = merchant["accumulated_charges"]
    return _quantize_amount(accumulated_amount + amount) >= cap


def _quantize_amount(amount):
    return amount.quantize(Decimal("0.01"))


class ChargeMerchantService:
    ZERO_AMOUNT = _quantize_amount(Decimal(0.0))

    def __init__(self, merchants_repository):
        self.merchants_repository = merchants_repository
        self._repo_lock = threading.Lock()
        self._merchant_locks = {}

    def charge_merchant(self, merchant_id: str, amount: Decimal) -> None:
        if not merchant_id or not isinstance(merchant_id, str):
            raise InvalidMerchantException
        if (
            not amount
            or not isinstance(amount, Decimal)
            or _quantize_amount(amount) <= self.ZERO_AMOUNT
        ):
            raise InvalidAmountException
        amount = _quantize_amount(amount)

        with self._repo_lock:
            if merchant_id not in self.merchants_repository:
                raise MerchantNotFoundException
            merchant = self.merchants_repository[merchant_id]

        with self._merchant_locks[merchant_id]:
            if _is_amount_exceeded(merchant, amount):
                raise AccumulatedAmountExceededException

            _charge_amount(merchant, amount)

    def register_merchant(self, merchant_id: str, cap: Decimal) -> None:
        if not merchant_id or not isinstance(merchant_id, str):
            raise InvalidMerchantException
        if (
            not cap
            or not isinstance(cap, Decimal)
            or _quantize_amount(cap) <= self.ZERO_AMOUNT
        ):
            raise InvalidCapException

        with self._repo_lock:
            if merchant_id in self.merchants_repository:
                raise AlreadyExistingMerchantException
            self.merchants_repository[merchant_id] = {
                "charges": [],
                "accumulated_charges": _quantize_amount(Decimal(0.0)),
                "charges_cap": _quantize_amount(cap),
            }
            self._merchant_locks[merchant_id] = threading.Lock()

    def get_cap_amount(self, merchant_id: str) -> dict[str, Decimal]:
        if not merchant_id or not isinstance(merchant_id, str):
            raise InvalidMerchantException
        with self._repo_lock:
            if merchant_id not in self.merchants_repository:
                raise MerchantNotFoundException
            merchant = self.merchants_repository[merchant_id]

        with self._merchant_locks[merchant_id]:
            cap = _quantize_amount(
                merchant["charges_cap"]
            )
            accumulated_charges = _quantize_amount(
                merchant["accumulated_charges"]
            )

        return {
            "cap": cap,
            "quota_left": _quantize_amount(cap - accumulated_charges),
            "accumulated_charges": accumulated_charges,
        }
