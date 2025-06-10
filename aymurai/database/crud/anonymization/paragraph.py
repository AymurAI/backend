import uuid

from sqlmodel import Session

from aymurai.database.schema import (
    AnonymizationParagraph,
    AnonymizationParagraphCreate,
    AnonymizationParagraphUpdate,
)
from aymurai.database.utils import text_to_uuid
from aymurai.logger import get_logger

logger = get_logger(__name__)


def anonymization_paragraph_create(
    paragraph_in: AnonymizationParagraphCreate,
    session: Session,
    override: bool = False,
) -> AnonymizationParagraph:
    new_paragraph = AnonymizationParagraph(**paragraph_in.model_dump())

    if override:
        existing = session.get(AnonymizationParagraph, new_paragraph.id)

        if existing:
            session.delete(existing)

    session.add(new_paragraph)
    session.commit()
    session.refresh(new_paragraph)
    return new_paragraph


def anonymization_paragraph_read(
    paragraph_id: uuid.UUID,
    session: Session,
) -> AnonymizationParagraph | None:
    return session.get(AnonymizationParagraph, paragraph_id)


def anonymization_paragraph_update(
    paragraph_id: uuid.UUID,
    paragraph_in: AnonymizationParagraphUpdate,
    session: Session,
) -> AnonymizationParagraph:
    paragraph = session.get(AnonymizationParagraph, paragraph_id)

    if not paragraph:
        raise ValueError(f"Paragraph not found: {paragraph_id}")

    for field, value in paragraph_in.model_dump(exclude_none=True).items():
        setattr(paragraph, field, value)

    session.add(paragraph)
    session.commit()
    session.refresh(paragraph)
    return paragraph


def anonymization_paragraph_delete(paragraph_id: uuid.UUID, session: Session):
    paragraph = session.get(AnonymizationParagraph, paragraph_id)

    if not paragraph:
        raise ValueError(f"Paragraph not found: {paragraph_id}")

    session.delete(paragraph)
    session.commit()

    return


# FIXME: This can be CLEARLY optimized
def anonymization_paragraph_batch_create_update(
    paragraphs_in: list[AnonymizationParagraphCreate], session: Session
) -> list[AnonymizationParagraph]:
    paragraphs = []

    for p_in in paragraphs_in:
        paragraph_id = text_to_uuid(p_in.text)

        paragraph = session.get(AnonymizationParagraph, paragraph_id)
        if paragraph:
            update = AnonymizationParagraphUpdate(**p_in.model_dump())

            for field, value in update.model_dump(exclude_none=True).items():
                setattr(paragraph, field, value)

        else:
            paragraph = AnonymizationParagraph(**p_in.model_dump())

        session.add(paragraph)
        session.commit()
        session.refresh(paragraph)

        paragraphs.append(paragraph)

    # refresh models (Must be a list or for-loop)
    [session.refresh(paragraph) for paragraph in paragraphs]

    return paragraphs
