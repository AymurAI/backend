from pydantic import UUID5
from fastapi import Body, Depends
from sqlmodel import Session, select
from fastapi.routing import APIRouter, HTTPException

from aymurai.database.utils import text_to_uuid
from aymurai.database.session import get_session
from aymurai.meta.api_interfaces import TextRequest, SuccessResponse
from aymurai.database.crud.anonymization.paragraph import (
    paragraph_read,
    paragraph_create,
    paragraph_delete,
    paragraph_update,
)
from aymurai.database.schema import (
    AnonymizationParagraph,
    AnonymizationParagraphRead,
    AnonymizationParagraphCreate,
    AnonymizationParagraphUpdate,
)

router = APIRouter()


@router.post("/paragraph", response_model=AnonymizationParagraphRead)
async def api_paragraph_create(
    paragraph_in: AnonymizationParagraphCreate,
    session: Session = Depends(get_session),
):
    """
    Add a new paragraph to the database
    """

    paragraph = paragraph_create(paragraph_in, session)
    return paragraph


@router.get("/paragraph", response_model=AnonymizationParagraphRead | None)
async def paragraph_read_by_text(
    data: TextRequest,
    session: Session = Depends(get_session),
) -> AnonymizationParagraphRead | None:
    paragraph_id = text_to_uuid(data.text)

    return paragraph_read(paragraph_id, session)


@router.post("/paragraph/text_to_uuid")
async def paragraph_get_uuid(text: str = Body(...)) -> str:
    return str(text_to_uuid(text))


@router.get("/paragraph/{paragraph_id}", response_model=AnonymizationParagraphRead)
async def api_paragraph_read(
    paragraph_id: UUID5,
    session: Session = Depends(get_session),
) -> AnonymizationParagraphRead:
    statement = select(AnonymizationParagraph).where(
        AnonymizationParagraph.id == paragraph_id
    )
    data = session.exec(statement).first()
    return data


@router.put("/paragraph/{paragraph_id}", response_model=AnonymizationParagraphRead)
async def api_paragraph_update(
    paragraph_id: UUID5,
    data: AnonymizationParagraphUpdate,
    session: Session = Depends(get_session),
) -> AnonymizationParagraphRead:
    try:
        paragraph = paragraph_update(paragraph_id, data, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return paragraph


@router.delete("/paragraph/{paragraph_id}", response_model=SuccessResponse)
async def api_paragraph_delete(
    paragraph_id: UUID5,
    session: Session = Depends(get_session),
):
    try:
        paragraph_delete(paragraph_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return SuccessResponse(id=paragraph_id, msg="Item deleted")


# @router.post("/document")
# async def document_add():
#     pass


# @router.get("/document/{document_id}")
# async def document_get():
#     pass


# @router.put("/document/{document_id}")
# async def document_update():
#     pass


# @router.delete("/document/{document_id}")
# async def document_delete():
#     pass
