import threading
import uuid
from dataclasses import dataclass, field


class ValidationError(Exception):
    pass


class InvalidIdempotencyKey(ValidationError):
    pass

class InvalidAmount(ValidationError):
    pass

class InvalidCurrency(ValidationError):
    pass

class ServiceError(Exception):
    pass
class PaymentNotFound(ServiceError):
    pass
class AmountOrCurrencyConflict(ServiceError):
    pass

@dataclass(frozen=True)
class PaymentDto:
    amount: int
    currency: str
    payment_id: str

@dataclass
class Payment:
    amount: int
    currency: str
    payment_id: uuid.UUID = field(default_factory=uuid.uuid4)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def to_dto(self) -> PaymentDto:
        return PaymentDto(self.amount, self.currency, str(self.payment_id))

    def check_amount_and_currency(self, amount, currency):
        if amount != self.amount or currency != self.currency:
            raise AmountOrCurrencyConflict


def _validate_uuid(uuid_input: str):
    try:
        uuid.UUID(str(uuid_input))
    except ValueError:
        raise InvalidIdempotencyKey(uuid_input)
def validate_idempotency_key(idempotency_key):
    _validate_uuid(idempotency_key)


def validate_amount(amount):
    if not isinstance(amount, int) or amount <= 0:
        raise InvalidAmount(amount)


def validate_currency(currency):
    if not isinstance(currency, str) or len(currency) < 2:
        raise InvalidCurrency(currency)


def validate_payment_id(payment_id):
    _validate_uuid(payment_id)


class PaymentService:
    def __init__(self):
        self._payments_by_idempotency_key: dict[str, Payment] = {}
        self._payments_by_payment_id: dict[str, Payment] = {}
        self._lock: threading.Lock = threading.Lock()

    def create_payment(self, idempotency_key: str, amount: int, currency: str) -> str:
        validate_idempotency_key(idempotency_key)
        validate_amount(amount)
        validate_currency(currency)
        payment = Payment(amount, currency)
        payment_id = str(payment.payment_id)

        with self._lock:
            if idempotency_key not in self._payments_by_idempotency_key:
                self._payments_by_idempotency_key[idempotency_key] = payment
                self._payments_by_payment_id[payment_id] = payment
                return payment_id
            payment = self._payments_by_idempotency_key[idempotency_key]

        payment.check_amount_and_currency(amount, currency)
        return str(payment.payment_id)

    def get_payment(self, payment_id: str) -> PaymentDto:
        validate_payment_id(payment_id)
        with self._lock:
            if payment_id not in self._payments_by_payment_id:
                raise PaymentNotFound
            payment = self._payments_by_payment_id[payment_id]
            return payment.to_dto()