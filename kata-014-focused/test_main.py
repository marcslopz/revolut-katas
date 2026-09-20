import uuid

from main import DocumentService, DocumentStatus, ActorRole


def test_create_document():
    service = DocumentService()

    document_id = service.create_document(str(uuid.uuid4()), "document title")


    document_dto = service.get_document(document_id)
    assert document_dto is not None
    assert document_dto.document_id == document_id
    assert document_dto.title == "document title"
    assert document_dto.status == DocumentStatus.CREATED


def test_delete_document():
    service = DocumentService()
    owner_id = str(uuid.uuid4())
    document_id = service.create_document(owner_id, "document title")
    
    service.delete_document(document_id, owner_id, str(ActorRole.REGULAR))
    
    document_dto = service.get_document(document_id)
    assert document_dto is not None
    assert document_dto.document_id == document_id
    assert document_dto.owner_id == owner_id
    assert document_dto.title == "document title"
    assert document_dto.status == DocumentStatus.DELETED
    