import threading
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class WalletDto:
    user_id: str
    balance: int
    wallet_id: str


@dataclass
class Transfer:
    wallet_src_id: str
    wallet_dst_id: str
    amount: int


@dataclass
class Wallet:
    user_id: str
    balance: int
    wallet_id: uuid.UUID = field(default_factory=uuid.uuid4)
    lock: threading.Lock = field(default_factory=threading.Lock)
    transfers: dict[str, Transfer] = field(default_factory=dict)

    def deposit_funds(self, amount):
        with self.lock:
            self.balance += amount

    def withdraw_funds(self, amount):
        with self.lock:
            if amount > self.balance:
                raise NotEnoughBalance(amount, self.balance)
            self.balance -= amount

    def to_dto(self):
        return WalletDto(
            user_id=self.user_id, balance=self.balance, wallet_id=str(self.wallet_id)
        )

    def transfer_to(self, wallet_dst: "Wallet", amount: int, idempotency_key: str):
        # atomic operation, we should lock wallets by alphabetically ordered wallet_ids
        # to avoid deadlocks
        if self.wallet_id < wallet_dst.wallet_id:
            first_lock = self.lock
            second_lock = wallet_dst.lock
        else:
            first_lock = wallet_dst.lock
            second_lock = self.lock
        with first_lock:
            with second_lock:
                if idempotency_key in self.transfers:
                    # already processed, do nothing
                    return
                if amount > self.balance:
                    raise NotEnoughBalance(amount, self.balance)
                wallet_dst.balance += amount
                wallet_dst.transfers[idempotency_key] = Transfer(
                    wallet_src_id=str(self.wallet_id),
                    wallet_dst_id=str(wallet_dst.wallet_id),
                    amount=amount,
                )
                self.balance -= amount
                self.transfers[idempotency_key] = Transfer(
                    wallet_src_id=str(self.wallet_id),
                    wallet_dst_id=str(wallet_dst.wallet_id),
                    amount=amount,
                )


class ValidationException(Exception):
    pass


class InvalidUserId(ValidationException):
    pass


class InvalidInitialBalance(ValidationException):
    pass


class InvalidWalletId(ValidationException):
    pass


class InvalidIdempotencyKey(ValidationException):
    pass


class InvalidAmount(ValidationException):
    pass


class ServiceException(Exception):
    pass


class WalletNotFound(ServiceException):
    pass


class NotEnoughBalance(ServiceException):
    pass


def validate_user_id(user_id):
    if not isinstance(user_id, str) or not user_id:
        raise InvalidUserId(user_id)


def validate_initial_balance(initial_balance):
    if not isinstance(initial_balance, int) or initial_balance < 0:
        raise InvalidInitialBalance(initial_balance)


def validate_wallet_id(wallet_id):
    try:
        uuid.UUID(str(wallet_id))
    except Exception:
        raise InvalidWalletId(wallet_id)


def validate_idempotency_key(idempotency_key):
    try:
        uuid.UUID(str(idempotency_key))
    except Exception:
        raise InvalidIdempotencyKey(idempotency_key)


def validate_operation_amount(amount):
    if not isinstance(amount, int) or amount <= 0:
        raise InvalidAmount(amount)


class WalletService:
    def __init__(self):
        self._wallets: dict[str, Wallet] = {}
        self._lock = threading.Lock()

    def create_wallet(self, user_id: str, initial_balance: int) -> str:
        validate_user_id(user_id)
        validate_initial_balance(initial_balance)
        wallet = Wallet(user_id, initial_balance)
        with self._lock:
            self._wallets[str(wallet.wallet_id)] = wallet
        return str(wallet.wallet_id)

    def get_wallet(self, wallet_id: str) -> WalletDto:
        validate_wallet_id(wallet_id)
        with self._lock:
            if wallet_id not in self._wallets:
                raise WalletNotFound(wallet_id)
            wallet_dto = self._wallets[wallet_id].to_dto()
        return wallet_dto

    def deposit_funds(self, wallet_id: str, amount: int) -> None:
        validate_wallet_id(wallet_id)
        validate_operation_amount(amount)
        with self._lock:
            if wallet_id not in self._wallets:
                raise WalletNotFound(wallet_id)
            wallet = self._wallets[wallet_id]

        wallet.deposit_funds(amount)

    def withdraw_funds(self, wallet_id: str, amount: int) -> None:
        validate_wallet_id(wallet_id)
        validate_operation_amount(amount)
        with self._lock:
            if wallet_id not in self._wallets:
                raise WalletNotFound(wallet_id)
            wallet = self._wallets[wallet_id]

        wallet.withdraw_funds(amount)

    def get_balance(self, wallet_id: str) -> int:
        validate_wallet_id(wallet_id)
        with self._lock:
            if wallet_id not in self._wallets:
                raise WalletNotFound(wallet_id)
            wallet_balance = self._wallets[wallet_id].balance

        return wallet_balance

    def transfer_funds(
        self, wallet_id_src: str, wallet_id_dst: str, amount: int, idempotency_key: str
    ) -> None:
        validate_wallet_id(wallet_id_src)
        validate_wallet_id(wallet_id_dst)
        validate_idempotency_key(idempotency_key)
        if wallet_id_dst == wallet_id_src:
            raise InvalidWalletId(wallet_id_src)
        validate_operation_amount(amount)
        with self._lock:
            if wallet_id_src not in self._wallets:
                raise WalletNotFound(wallet_id_src)
            if wallet_id_dst not in self._wallets:
                raise WalletNotFound(wallet_id_dst)
            wallet_src = self._wallets[wallet_id_src]
            wallet_dst = self._wallets[wallet_id_dst]
        wallet_src.transfer_to(wallet_dst, amount, idempotency_key)
