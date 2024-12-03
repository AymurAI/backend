import uuid

from sqlmodel import Session, select

from aymurai.logger import get_logger
from aymurai.database.schema import (
    DataPublicDocument,
    DataPublicParagraph,
    DataPublicDocumentUpdate,
)

logger = get_logger(__name__)


def datapublic_document_create(
    id: uuid.UUID,
    name: str,
    paragraphs: list[DataPublicParagraph],
    session: Session,
    override: bool = False,
) -> DataPublicDocument:
    document = DataPublicDocument(id=id, name=name, paragraphs=paragraphs)

    if override:
        statement = select(DataPublicDocument).where(
            DataPublicDocument.id == document.id
        )
        existing = session.exec(statement).first()

        if existing:
            session.delete(existing)

    session.add(document)
    session.commit()
    session.refresh(document)

    return document


def datapublic_document_read(
    document_id: uuid.UUID,
    session: Session,
) -> DataPublicDocument | None:
    statement = select(DataPublicDocument).where(DataPublicDocument.id == document_id)
    data = session.exec(statement).first()
    return data


def datapublic_document_update(
    document_id: uuid.UUID,
    document_in: DataPublicDocumentUpdate,
    session: Session,
) -> DataPublicDocument:
    statement = select(DataPublicDocument).where(DataPublicDocument.id == document_id)
    document = session.exec(statement).first()

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    for field, value in document_in.model_dump(exclude_unset=True).items():
        setattr(document, field, value)

    return datapublic_document_create(document, session)


def datapublic_document_delete(document_id: uuid.UUID, session: Session):
    statement = select(DataPublicDocument).where(DataPublicDocument.id == document_id)
    document = session.exec(statement).first()

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    session.delete(document)
    session.commit()

    return
