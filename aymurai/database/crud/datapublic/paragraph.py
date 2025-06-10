import uuid

from sqlmodel import Session, select

from aymurai.database.schema import (
    DataPublicParagraph,
    DataPublicParagraphCreate,
    DataPublicParagraphUpdate,
)
from aymurai.database.utils import text_to_uuid
from aymurai.logger import get_logger

logger = get_logger(__name__)


def datapublic_paragraph_create(
    paragraph_in: DataPublicParagraphCreate,
    session: Session,
    override: bool = False,
) -> DataPublicParagraph:
    paragraph = DataPublicParagraph(**paragraph_in.model_dump())

    if override:
        statement = select(DataPublicParagraph).where(
            DataPublicParagraph.id == paragraph.id
        )
        existing = session.exec(statement).first() or paragraph

        if existing:
            session.delete(existing)

    session.add(paragraph)
    session.commit()
    session.refresh(paragraph)
    return paragraph


def datapublic_paragraph_read(
    paragraph_id: uuid.UUID,
    session: Session,
) -> DataPublicParagraph | None:
    statement = select(DataPublicParagraph).where(
        DataPublicParagraph.id == paragraph_id
    )
    data = session.exec(statement).first()
    return data


def datapublic_paragraph_update(
    paragraph_id: uuid.UUID,
    paragraph_in: DataPublicParagraphUpdate,
    session: Session,
) -> DataPublicParagraph:
    statement = select(DataPublicParagraph).where(
        DataPublicParagraph.id == paragraph_id
    )
    paragraph = session.exec(statement).first()

    if not paragraph:
        raise ValueError(f"Paragraph not found: {paragraph_id}")

    for field, value in paragraph_in.model_dump(exclude_none=True).items():
        setattr(paragraph, field, value)

    return datapublic_paragraph_create(paragraph, session)


def datapublic_paragraph_delete(paragraph_id: uuid.UUID, session: Session):
    statement = select(DataPublicParagraph).where(
        DataPublicParagraph.id == paragraph_id
    )
    paragraph = session.exec(statement).first()

    if not paragraph:
        raise ValueError(f"Paragraph not found: {paragraph_id}")

    session.delete(paragraph)
    session.commit()

    return


def datapublic_paragraph_batch_create_update(
    paragraphs_in: list[DataPublicParagraphCreate], session: Session
) -> list[DataPublicParagraph]:
    paragraphs = []

    for paragraph_in in paragraphs_in:
        paragraph_id = text_to_uuid(paragraph_in.text)

        statement = select(DataPublicParagraph).where(
            DataPublicParagraph.id == paragraph_id
        )
        paragraph = session.exec(statement).first()
        if paragraph:
            update = DataPublicParagraphUpdate(**paragraph_in.model_dump())

            for field, value in update.model_dump(exclude_none=True).items():
                setattr(paragraph, field, value)

        else:
            paragraph = DataPublicParagraph(**paragraph_in.model_dump())

        paragraphs.append(paragraph)

        session.add(paragraph)
        session.commit()

    # refresh models (Must be a list or for-loop)
    [session.refresh(paragraph) for paragraph in paragraphs]

    return paragraphs
