import threading
import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class OperationType(StrEnum):
    EARN = "earn"
    REDEEM = "redeem"
    TRANSFER_FROM = "transfer_from"
    TRANSFER_TO = "transfer_to"


@dataclass(frozen=True)
class OperationDto:
    type: str
    points: int
    transfer_to_or_from: str | None


@dataclass
class Operation:
    type: OperationType
    points: int
    transfer_to_or_from: uuid.UUID | None = None

    def to_dto(self) -> OperationDto:
        return OperationDto(
            self.type.value,
            self.points,
            str(self.transfer_to_or_from) if self.transfer_to_or_from else None,
        )


@dataclass
class Account:
    balance: int
    account_id: uuid.UUID = field(default_factory=uuid.uuid4)
    operations: list[Operation] = field(default_factory=list)

    def earn_points(self, points):
        self.balance += points
        self.operations.append(Operation(OperationType.EARN, points))

    def redeem_points(self, points):
        if points > self.balance:
            raise NotEnoughPoints(self.balance, points)
        self.balance -= points
        self.operations.append(Operation(OperationType.REDEEM, points))

    def to_operations_dto(self) -> list[OperationDto]:
        return [operation.to_dto() for operation in self.operations]

    def transfer_to(self, to_account: "Account", points: int):
        if points > self.balance:
            raise NotEnoughPoints(self.balance, points)
        self.balance -= points
        to_account.balance += points
        self.operations.append(
            Operation(OperationType.TRANSFER_TO, points, to_account.account_id)
        )
        to_account.operations.append(
            Operation(OperationType.TRANSFER_FROM, points, self.account_id)
        )


class ValidationException(Exception):
    pass


class InvalidBalance(ValidationException):
    pass


class InvalidPoints(ValidationException):
    pass


class InvalidUuid(ValidationException):
    pass


class ServiceException(Exception):
    pass


class AccountNotFound(ServiceException):
    pass


class NotEnoughPoints(ServiceException):
    pass


def validate_balance(initial_balance):
    if not isinstance(initial_balance, int) or initial_balance < 0:
        raise InvalidBalance(initial_balance)


def validate_points(points):
    if not isinstance(points, int) or points <= 0:
        raise InvalidPoints(points)


def get_uuid_from_str(uuid_string) -> uuid.UUID:
    try:
        return uuid.UUID(str(uuid_string))
    except ValueError:
        raise InvalidUuid(uuid_string)


class AccountService:
    def __init__(self):
        self._accounts: dict[uuid.UUID, Account] = {}
        self._lock = threading.Lock()

    def create_account(self, initial_balance: int) -> str:
        validate_balance(initial_balance)
        new_account = Account(initial_balance)
        with self._lock:
            self._accounts[new_account.account_id] = new_account
        return str(new_account.account_id)

    def earn_points(self, account_id: str, points: int):
        validate_points(points)
        account_uuid = get_uuid_from_str(account_id)
        with self._lock:
            if account_uuid not in self._accounts:
                raise AccountNotFound(account_id)
            account = self._accounts[account_uuid]
            account.earn_points(points)

    def redeem_points(self, account_id: str, points: int):
        validate_points(points)
        account_uuid = get_uuid_from_str(account_id)
        with self._lock:
            if account_uuid not in self._accounts:
                raise AccountNotFound(account_id)
            account = self._accounts[account_uuid]
            account.redeem_points(points)

    def get_balance(self, account_id: str) -> int:
        account_uuid = get_uuid_from_str(account_id)
        with self._lock:
            if account_uuid not in self._accounts:
                raise AccountNotFound(account_id)
            account = self._accounts[account_uuid]
            return account.balance

    def get_account_operations(self, account_id: str) -> list[OperationDto]:
        account_uuid = get_uuid_from_str(account_id)
        with self._lock:
            if account_uuid not in self._accounts:
                raise AccountNotFound(account_id)
            account = self._accounts[account_uuid]
            return account.to_operations_dto()

    def transfer_points(
        self, from_account_id: str, to_account_id: str, points: int
    ) -> None:
        from_account_uuid = get_uuid_from_str(from_account_id)
        to_account_uuid = get_uuid_from_str(to_account_id)
        validate_points(points)
        with self._lock:
            if from_account_uuid not in self._accounts:
                raise AccountNotFound(from_account_id)
            if to_account_uuid not in self._accounts:
                raise AccountNotFound(to_account_id)
            from_account = self._accounts[from_account_uuid]
            to_account = self._accounts[to_account_uuid]
            from_account.transfer_to(to_account, points)
