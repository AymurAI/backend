import uuid

from sqlmodel import Session, select

from aymurai.logger import get_logger
from aymurai.database.schema import (
    AnonymizationDocument,
    AnonymizationParagraph,
    AnonymizationDocumentUpdate,
)

logger = get_logger(__name__)


def anonymization_document_create(
    id: uuid.UUID,
    name: str,
    paragraphs: list[AnonymizationParagraph],
    session: Session,
    override: bool = False,
) -> AnonymizationDocument:
    document = AnonymizationDocument(id=id, name=name, paragraphs=paragraphs)

    if override:
        statement = select(AnonymizationDocument).where(
            AnonymizationDocument.id == document.id
        )
        existing = session.exec(statement).first()

        if existing:
            session.delete(existing)

    session.add(document)
    session.commit()
    session.refresh(document)

    return document


def anonymization_document_read(
    document_id: uuid.UUID,
    session: Session,
) -> AnonymizationDocument | None:
    statement = select(AnonymizationDocument).where(
        AnonymizationDocument.id == document_id
    )
    data = session.exec(statement).first()
    return data


def anonymization_document_update(
    document_id: uuid.UUID,
    document_in: AnonymizationDocumentUpdate,
    session: Session,
) -> AnonymizationDocument:
    statement = select(AnonymizationDocument).where(
        AnonymizationDocument.id == document_id
    )
    document = session.exec(statement).first()

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    for field, value in document_in.model_dump(exclude_unset=True).items():
        setattr(document, field, value)

    return anonymization_document_create(document, session)


def anonymization_document_delete(document_id: uuid.UUID, session: Session):
    statement = select(AnonymizationDocument).where(
        AnonymizationDocument.id == document_id
    )
    document = session.exec(statement).first()

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    session.delete(document)
    session.commit()

    return
