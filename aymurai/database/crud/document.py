import uuid

from sqlmodel import Session, select

from aymurai.logger import get_logger
from aymurai.database.schema import (
    Document,
    Paragraph,
    DocumentUpdate,
)

logger = get_logger(__name__)


def document_create(
    id: uuid.UUID,
    name: str,
    paragraphs: list[Paragraph],
    session: Session,
) -> Document:
    document = Document(id=id, name=name, paragraphs=paragraphs)

    exists = session.get(Document, id)
    if exists:
        logger.warning(f"Document already exists: {id}. skipping creation.")
        return exists

    session.add(document)
    session.commit()
    session.refresh(document)

    return document


def document_read(
    document_id: uuid.UUID,
    session: Session,
) -> Document | None:
    statement = select(Document).where(Document.id == document_id)
    data = session.exec(statement).first()
    return data


def document_update(
    document_id: uuid.UUID,
    document_in: DocumentUpdate,
    session: Session,
) -> Document:
    statement = select(Document).where(Document.id == document_id)
    document = session.exec(statement).first()

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    for field, value in document_in.model_dump(exclude_unset=True).items():
        setattr(document, field, value)

    return document_create(document, session)


def document_delete(document_id: uuid.UUID, session: Session):
    statement = select(Document).where(Document.id == document_id)
    document = session.exec(statement).first()

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    session.delete(document)
    session.commit()

    return
