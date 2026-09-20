import threading
import uuid
from dataclasses import dataclass, field


@dataclass
class Transfer:
    from_account_id: str
    to_account_id: str
    amount: int
    transfer_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class Account:
    account_id: str
    balance: int
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        if self.balance < 0:
            raise ValueError(f"Invalid balance: {self.balance}")
        validate_account_id(self.account_id)

    def transfer_to(self, to_account: "Account", amount: int) -> None:
        if self.balance < amount:
            raise ValueError(
                f"Not enough balance for transfer on source account: {self.account_id}, {self.balance}, {amount}"
            )
        self.balance -= amount
        to_account.balance += amount


def validate_account_id(account_id):
    if not isinstance(account_id, str) or not account_id:
        raise ValueError(f"Invalid account_id: {account_id}")


class AccountService:
    def __init__(self):
        self._accounts: dict[str, Account] = dict()
        self._transfers: dict[str, Transfer] = dict()
        self._lock = threading.Lock()

    def create_account(self, account_id: str, balance: int) -> None:
        with self._lock:
            self._accounts[account_id] = Account(account_id, balance)

    def transfer(self, from_account_id: str, to_account_id: str, amount: int) -> None:
        validate_account_id(from_account_id)
        validate_account_id(to_account_id)
        if from_account_id == to_account_id:
            raise ValueError(
                f"Cannot transfer {from_account_id} to {to_account_id}, they're the same account"
            )
        with self._lock:
            from_account = self._accounts[from_account_id]
            to_account = self._accounts[to_account_id]

        account_to_lock_first = (
            from_account if from_account_id < to_account_id else to_account
        )
        account_to_lock_second = (
            to_account if from_account_id < to_account_id else from_account
        )
        with account_to_lock_first.lock:
            with account_to_lock_second.lock:
                from_account.transfer_to(to_account, amount)

        transfer = Transfer(from_account_id, to_account_id, amount)
        with self._lock:
            self._transfers[str(transfer.transfer_id)] = transfer
