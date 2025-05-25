from fastapi import Depends, HTTPException
from fastapi.routing import APIRouter
from more_itertools import flatten
from pydantic import UUID4, UUID5
from sqlmodel import Session

from aymurai.database.crud.prediction import (
    read_document_prediction_paragraphs,
)
from aymurai.database.meta.document import Document
from aymurai.database.schema import (
    ModelType,
)
from aymurai.database.session import get_session
from aymurai.logger import get_logger
from aymurai.meta.entities import DocLabel
from aymurai.settings import settings

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH


router = APIRouter()


# MARK: Get Document labels
@router.get("/pipeline/{pipeline_type}/document/{document_id}")
async def get_document_labels(
    document_id: UUID4 | UUID5,
    pipeline_type: ModelType,
    session: Session = Depends(get_session),
) -> list[DocLabel]:
    # ———————— Sanity check ——————————————————————————————————————————————————————————
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id}",
        )

    annotations = read_document_prediction_paragraphs(
        session=session,
        document_id=document_id,
        model_type=pipeline_type,
    )

    labels = [para.prediction.labels for para in annotations if para.prediction]
    return list(flatten(labels))
