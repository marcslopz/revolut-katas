import threading
import uuid
from dataclasses import dataclass, field


class ServiceException(Exception):
    pass


class AccountNotFound(ServiceException):
    pass


class NotEnoughBalance(ServiceException):
    pass


class SameAccountForTransfer(ServiceException):
    pass


class IdempotencyConflict(ServiceException):
    pass


@dataclass
class Account:
    user_id: str
    balance: int
    account_id: uuid.UUID = field(default_factory=uuid.uuid4)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def deposit(self, amount: int) -> None:
        with self.lock:
            self._deposit(amount)

    def _deposit(self, amount: int) -> None:
        self.balance += amount

    def withdraw(self, amount) -> None:
        with self.lock:
            self._withdraw(amount)

    def _withdraw(self, amount: int) -> None:
        if amount > self.balance:
            raise NotEnoughBalance(self.user_id, amount)
        self.balance -= amount

    def transfer_to(self, account_dst: "Account", amount: int):
        if self.account_id < account_dst.account_id:
            lock_first = self.lock
            lock_second = account_dst.lock
        else:
            lock_first = account_dst.lock
            lock_second = self.lock
        with lock_first:
            with lock_second:
                self._withdraw(amount)
                account_dst._deposit(amount)


def validate_user_id(user_id: str):
    if not isinstance(user_id, str) or not user_id:
        raise ValueError(user_id)


def validate_balance(balance: int):
    if not isinstance(balance, int) or balance < 0:
        raise ValueError(balance)


def validate_account_id(account_id) -> uuid.UUID:
    return uuid.UUID(str(account_id))


def validate_amount(amount):
    pass


class AccountService:
    def __init__(self):
        self._accounts: dict[uuid.UUID, Account] = dict()
        self._idempotency_keys: dict[str, tuple[uuid.UUID, uuid.UUID, int]] = {}
        self._lock = threading.Lock()

    def create_account(self, user_id: str, balance: int) -> str:
        validate_user_id(user_id)
        validate_balance(balance)
        account = Account(user_id, balance)
        with self._lock:
            self._accounts[account.account_id] = account
        return str(account.account_id)

    def deposit_amount(self, account_id: str, amount: int) -> None:
        account_uuid = validate_account_id(account_id)
        validate_amount(amount)
        with self._lock:
            if account_uuid not in self._accounts:
                raise AccountNotFound(account_id)
            account = self._accounts[account_uuid]
        account.deposit(amount)

    def withdraw_amount(self, account_id: str, amount: int) -> None:
        account_uuid = validate_account_id(account_id)
        validate_amount(amount)
        with self._lock:
            if account_uuid not in self._accounts:
                raise AccountNotFound(account_id)
            account = self._accounts[account_uuid]
        account.withdraw(amount)

    def get_account_balance(self, account_id: str) -> int:
        account_uuid = validate_account_id(account_id)
        with self._lock:
            if account_uuid not in self._accounts:
                raise AccountNotFound(account_id)
            account = self._accounts[account_uuid]
        return account.balance

    def transfer_amount(
        self,
        idempotency_key: str,
        account_id_src: str,
        account_id_dst: str,
        amount: int,
    ) -> None:
        account_uuid_src = validate_account_id(account_id_src)
        account_uuid_dst = validate_account_id(account_id_dst)
        if account_id_dst == account_id_src:
            raise SameAccountForTransfer(account_id_src)
        validate_amount(amount)

        with self._lock:
            if idempotency_key in self._idempotency_keys:
                saved_account_uuid_src, saved_account_uuid_dst, saved_amount = (
                    self._idempotency_keys[idempotency_key]
                )
                if (
                    saved_account_uuid_src != account_uuid_src
                    or saved_account_uuid_dst != account_uuid_dst
                    or saved_amount != amount
                ):
                    raise IdempotencyConflict(
                        idempotency_key, account_id_src, account_id_dst, amount
                    )
                return
            if account_uuid_src not in self._accounts:
                raise AccountNotFound(account_id_src)
            if account_uuid_dst not in self._accounts:
                raise AccountNotFound(account_id_dst)
            account_src = self._accounts[account_uuid_src]
            account_dst = self._accounts[account_uuid_dst]
            account_src.transfer_to(account_dst, amount)
            self._idempotency_keys[idempotency_key] = (
                account_uuid_src,
                account_uuid_dst,
                amount,
            )

