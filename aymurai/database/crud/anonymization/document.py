import uuid

from sqlmodel import Session, select

from aymurai.logger import get_logger
from aymurai.database.schema import (
    AnonymizationDocument,
    AnonymizationParagraph,
    AnonymizationDocumentCreate,
    AnonymizationDocumentUpdate,
    AnonymizationDocumentParagraph,
)

logger = get_logger(__name__)


def document_create(
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

    # paragraph_links = [
    #     AnonymizationDocumentParagraph(
    #         document_id=document.id, paragraph_id=paragraph.id, order=i
    #     )
    #     for i, paragraph in enumerate(document_in.paragraphs)
    # ]
    # session.add_all(paragraph_links)
    # session.commit()
    # for i, paragraph in enumerate(document_in.paragraphs):
    #     link = AnonymizationDocumentParagraph(
    #         document_id=document.id, paragraph_id=paragraph.id, order=i
    #     )
    #     session.add(link)
    #     session.commit()

    # paragraph_links = []
    # for i, paragraph_in in enumerate(document_in.paragraphs):
    #     statement = (
    #         select(AnonymizationDocumentParagraph)
    #         .where(AnonymizationDocumentParagraph.document_id == document.id)
    #         .where(AnonymizationDocumentParagraph.paragraph_id == paragraph_in.id)
    #     )
    #     link = session.exec(statement).first()
    #     if not link:
    #         link = AnonymizationDocumentParagraph(
    #             document_id=document.id, paragraph_id=paragraph_in.id, order=i
    #         )

    #     paragraph_links.append(link)

    # session.add_all(paragraph_links)
    # session.commit()

    return document


def document_read(
    document_id: uuid.UUID,
    session: Session,
) -> AnonymizationDocument | None:
    statement = select(AnonymizationDocument).where(
        AnonymizationDocument.id == document_id
    )
    data = session.exec(statement).first()
    return data


def document_update(
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

    return document_create(document, session)


def document_delete(document_id: uuid.UUID, session: Session):
    statement = select(AnonymizationDocument).where(
        AnonymizationDocument.id == document_id
    )
    document = session.exec(statement).first()

    if not document:
        raise ValueError(f"Document not found: {document_id}")

    session.delete(document)
    session.commit()

    return
