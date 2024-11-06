import uuid

from fastapi import Depends
from sqlmodel import Session, select
from fastapi.routing import APIRouter

from aymurai.database.utils import text_to_uuid
from aymurai.database.session import get_session
from aymurai.meta.api_interfaces import SuccessResponse
from aymurai.database.schema import (
    AnonymizationParagraph,
    AnonymizationParagraphRead,
    AnonymizationParagraphCreate,
    AnonymizationParagraphUpdate,
)

router = APIRouter()


@router.post("/paragraph", response_model=AnonymizationParagraphRead)
async def paragraph_add(
    data: AnonymizationParagraphCreate,
    session: Session = Depends(get_session),
):

    item = AnonymizationParagraph(**data.model_dump())

    retrieve = session.get(AnonymizationParagraph, item.id)
    if retrieve:
        return retrieve

    session.add(item)
    session.commit()
    session.refresh(item)

    return item


@router.get("/paragraph", response_model=AnonymizationParagraphRead)
async def paragraph_get_by_text(
    text: str,
    session: Session = Depends(get_session),
) -> AnonymizationParagraphRead:
    paragraph_id = text_to_uuid(text)

    statement = select(AnonymizationParagraph).where(
        AnonymizationParagraph.id == paragraph_id
    )
    data = session.exec(statement).first()
    return data


@router.get("/paragraph/text_to_uuid")
async def paragraph_get_uuid(text: str) -> str:
    return str(text_to_uuid(text))


@router.get("/paragraph/{paragraph_id}", response_model=AnonymizationParagraphRead)
async def paragraph_get(
    paragraph_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> AnonymizationParagraphRead:

    statement = select(AnonymizationParagraph).where(
        AnonymizationParagraph.id == paragraph_id
    )
    data = session.exec(statement).first()
    return data


@router.put("/paragraph/{paragraph_id}", response_model=AnonymizationParagraphRead)
async def paragraph_update(
    paragraph_id: uuid.UUID,
    data: AnonymizationParagraphUpdate,
    session: Session = Depends(get_session),
) -> AnonymizationParagraphRead:

    statement = select(AnonymizationParagraph).where(
        AnonymizationParagraph.id == paragraph_id
    )
    data_db = session.exec(statement).first()

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(data_db, field, value)

    session.add(data_db)
    session.commit()
    session.refresh(data_db)

    return data_db


@router.delete("/paragraph/{paragraph_id}", response_model=SuccessResponse)
async def paragraph_delete(
    paragraph_id: uuid.UUID,
    session: Session = Depends(get_session),
):

    statement = select(AnonymizationParagraph).where(
        AnonymizationParagraph.id == paragraph_id
    )
    data = session.exec(statement).first()
    session.delete(data)
    session.commit()

    return SuccessResponse(id=paragraph_id, msg="Item deleted")
