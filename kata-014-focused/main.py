import dataclasses
import threading
import uuid
from enum import StrEnum, auto


class ValidationException(Exception):
    pass


class InvalidUuid(ValidationException):
    pass


class InvalidTitle(ValidationException):
    pass

class InvalidActorRole(ValidationException):
    pass


class ServiceException(Exception):
    pass


class DocumentNotFound(ServiceException):
    pass


class DeletionDenied(ServiceException):
    pass


def get_uuid_from_str(uuid_str):
    try:
        return uuid.UUID(str(uuid_str))
    except ValueError:
        raise InvalidUuid(uuid_str)


class DocumentStatus(StrEnum):
    CREATED = auto()
    DELETED = auto()


class ActorRole(StrEnum):
    ADMIN = auto()
    REGULAR = auto()

@dataclasses.dataclass(frozen=True)
class DocumentDto:
    document_id: str
    owner_id: str
    title: str
    status: str

@dataclasses.dataclass
class Document:
    owner_id: uuid.UUID
    title: str
    status: DocumentStatus = DocumentStatus.CREATED
    document_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)

    def _validate_title(self) -> None:
        if not isinstance(self.title, str) or not self.title:
            raise InvalidTitle(self.title)

    def __post_init__(self):
        self.owner_id = get_uuid_from_str(self.owner_id)
        self._validate_title()

    def delete(self, actor_uuid: uuid.UUID, actor_role: ActorRole) -> None:
        if actor_uuid != self.owner_id and actor_role != ActorRole.ADMIN:
            raise DeletionDenied(self.document_id, actor_uuid)
        self.status = DocumentStatus.DELETED

    def to_dto(self) -> DocumentDto:
        return DocumentDto(str(self.document_id), str(self.owner_id), self.title, str(self.status))


def get_role_from_str(actor_role_str: str) -> ActorRole:
    try:
        return ActorRole(actor_role_str)
    except ValueError:
        raise InvalidActorRole(actor_role_str)


class DocumentService:
    def __init__(self):
        self._documents: dict[uuid.UUID, Document] = {}
        self._lock = threading.Lock()

    def create_document(self, owner_id: str, title: str) -> str:
        # noinspection bad-argument-type
        document = Document(owner_id, title)
        with self._lock:
            self._documents[document.document_id] = document
        return str(document.document_id)

    def delete_document(self, document_id: str, actor_id: str, actor_role: str) -> None:
        actor_role_enum = get_role_from_str(actor_role)
        document_uuid = get_uuid_from_str(document_id)
        actor_uuid = get_uuid_from_str(actor_id)
        with self._lock:
            document = self._get_document_by_id(document_uuid)
            document.delete(actor_uuid, actor_role_enum)

    def _get_document_by_id(self, document_uuid: uuid.UUID) -> Document:
        try:
            return self._documents[document_uuid]
        except KeyError:
            raise DocumentNotFound(document_uuid)

    def get_document(self, document_id: str) -> DocumentDto:
        document_uuid = get_uuid_from_str(document_id)
        with self._lock:
            document = self._get_document_by_id(document_uuid)
            return document.to_dto()
