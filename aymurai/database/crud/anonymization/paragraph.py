import uuid

from sqlmodel import Session, select

from aymurai.logger import get_logger
from aymurai.database.utils import text_to_uuid
from aymurai.database.schema import (
    AnonymizationParagraph,
    AnonymizationParagraphCreate,
    AnonymizationParagraphUpdate,
)

logger = get_logger(__name__)


def paragraph_create(
    paragraph_in: AnonymizationParagraphCreate,
    session: Session,
    override: bool = False,
) -> AnonymizationParagraph:
    paragraph = AnonymizationParagraph(**paragraph_in.model_dump())

    if override:
        statement = select(AnonymizationParagraph).where(
            AnonymizationParagraph.id == paragraph.id
        )
        existing = session.exec(statement).first() or paragraph

        if existing:
            session.delete(existing)

    session.add(paragraph)
    session.commit()
    session.refresh(paragraph)
    return paragraph


def paragraph_read(
    paragraph_id: uuid.UUID,
    session: Session,
) -> AnonymizationParagraph | None:
    statement = select(AnonymizationParagraph).where(
        AnonymizationParagraph.id == paragraph_id
    )
    data = session.exec(statement).first()
    return data


def paragraph_update(
    paragraph_id: uuid.UUID,
    paragraph_in: AnonymizationParagraphUpdate,
    session: Session,
) -> AnonymizationParagraph:
    statement = select(AnonymizationParagraph).where(
        AnonymizationParagraph.id == paragraph_id
    )
    paragraph = session.exec(statement).first()

    if not paragraph:
        raise ValueError(f"Paragraph not found: {paragraph_id}")

    for field, value in paragraph_in.model_dump(exclude_unset=True).items():
        setattr(paragraph, field, value)

    return paragraph_create(paragraph, session)


def paragraph_delete(paragraph_id: uuid.UUID, session: Session):
    statement = select(AnonymizationParagraph).where(
        AnonymizationParagraph.id == paragraph_id
    )
    paragraph = session.exec(statement).first()

    if not paragraph:
        raise ValueError(f"Paragraph not found: {paragraph_id}")

    session.delete(paragraph)
    session.commit()

    return


# FIXME: This can be CLEARLY optimized
def paragraph_batch_create_update(
    paragraphs_in: list[AnonymizationParagraphCreate], session: Session
) -> list[AnonymizationParagraph]:
    paragraphs = []

    for paragraph_in in paragraphs_in:
        paragraph_id = text_to_uuid(paragraph_in.text)

        statement = select(AnonymizationParagraph).where(
            AnonymizationParagraph.id == paragraph_id
        )
        paragraph = session.exec(statement).first()
        if paragraph:
            update = AnonymizationParagraphUpdate(**paragraph_in.model_dump())

            for field, value in update.model_dump(exclude_unset=True).items():
                setattr(paragraph, field, value)

        else:
            paragraph = AnonymizationParagraph(**paragraph_in.model_dump())

        paragraphs.append(paragraph)

        session.add(paragraph)
        session.commit()

    # refresh models (Must be a list or for-loop)
    [session.refresh(paragraph) for paragraph in paragraphs]

    return paragraphs
