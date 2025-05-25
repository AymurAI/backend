from fastapi import Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from pydantic import UUID4, UUID5
from sqlmodel import Session, select
from starlette.status import HTTP_201_CREATED

from aymurai.database.schema import (
    Datapublic,
    DatapublicFormat,
    DatapublicPublic,
    ModelType,
)
from aymurai.database.session import get_session
from aymurai.logger import get_logger

logger = get_logger(__name__)


router = APIRouter()


# MARK: GET Validation Document
@router.get(f"/pipeline/{ModelType.DATAPUBLIC}/document/{{document_id}}/validation")
async def datapublic_get_document_validation(
    document_id: UUID4 | UUID5,
    session: Session = Depends(get_session),
) -> DatapublicPublic:
    statement = select(Datapublic).where(Datapublic.fk_document == document_id)
    datapublic = session.exec(statement).first()
    if not datapublic:
        raise HTTPException(
            status_code=404,
            detail=f"datapublic validation not found for document: {document_id}",
        )

    logger.info(f"datapublic validation loaded for document: {document_id}")

    return DatapublicPublic.model_validation(datapublic)


# MARK: POST Validation Document
@router.post(f"/pipeline/{ModelType.DATAPUBLIC}/document/{{document_id}}/validation")
async def datapublic_save_document_validation(
    document_id: UUID4 | UUID5,
    records: dict = Body(..., example={}),
    validation_format: DatapublicFormat = DatapublicFormat.NONE,
    session: Session = Depends(get_session),
) -> JSONResponse:
    logger.info(f"processing annotations => {document_id}")

    statement = select(Datapublic).where(Datapublic.fk_document == document_id)
    datapublic = session.exec(statement).first()
    if not datapublic:
        datapublic = Datapublic(
            fk_document=document_id,
            records={},
            validation_format=validation_format,
        )

    match validation_format:
        case DatapublicFormat.NONE:
            logger.info(f"validation format: {validation_format}. skipping")
        case _:
            NotImplementedError(
                f"validation format: {validation_format} not implemented"
            )

    datapublic.records = records
    datapublic.validation_format = validation_format

    session.add(datapublic)
    session.commit()

    logger.info(f"datapublic validation saved for document: {document_id}")

    return JSONResponse(
        status_code=HTTP_201_CREATED,
        content={"message": f"datapublic validation saved for document: {document_id}"},
    )
