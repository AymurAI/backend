import os
from threading import Lock

import torch
from pydantic import UUID5
from sqlmodel import Session
from fastapi import Body, Depends
from fastapi.routing import APIRouter

from aymurai.logger import get_logger
from aymurai.settings import settings
from aymurai.utils.misc import get_element
from aymurai.api.utils import load_pipeline
from aymurai.database.utils import text_to_uuid
from aymurai.database.session import get_session
from aymurai.database.crud.datapublic.document import datapublic_document_create
from aymurai.meta.api_interfaces import (
    DocLabel,
    TextRequest,
    DocumentAnnotations,
    DocumentInformation,
)
from aymurai.database.schema import (
    DataPublicParagraph,
    DataPublicParagraphCreate,
    DataPublicParagraphUpdate,
)
from aymurai.database.crud.datapublic.paragraph import (
    datapublic_paragraph_read,
    datapublic_paragraph_create,
    datapublic_paragraph_update,
    datapublic_paragraph_batch_create_update,
)

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH
torch.set_num_threads = 100  # FIXME: polemic ?
pipeline_lock = Lock()


router = APIRouter()


# MARK: Predict
@router.post("/predict", response_model=DocumentInformation)
async def predict_over_text(
    text_request: TextRequest = Body({"text": "Buenos Aires, 17 de noviembre 2024"}),
    use_cache: bool = True,
    session: Session = Depends(get_session),
) -> DocumentInformation:
    logger.info("datapublic predict single")

    logger.info(f"Checking cache (use cache: {use_cache})")
    text = text_request.text
    paragraph_id = text_to_uuid(text)

    cached_prediction = datapublic_paragraph_read(paragraph_id, session=session)
    if cached_prediction and use_cache:
        logger.info(f"cache loaded from key: {paragraph_id}")
        logger.info(f"{cached_prediction}")
        return DocumentInformation(
            document=cached_prediction.text,
            labels=cached_prediction.prediction or [],
        )

    # load datapublic pipeline
    logger.info("Running prediction")
    item = [{"path": "empty", "data": {"doc.text": text_request.text}}]
    pipeline = load_pipeline(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "full-paragraph")
    )

    with pipeline_lock:
        processed = pipeline.preprocess(item)
        processed = pipeline.predict_single(processed[0])
        processed = pipeline.postprocess([processed])

    new_prediction = DocumentInformation(
        document=get_element(processed[0], ["data", "doc.text"]) or "",
        labels=get_element(processed[0], ["predictions", "entities"]) or [],
    )

    logger.info(f"saving in cache: {new_prediction}")
    if use_cache:
        if not cached_prediction:
            paragraph = DataPublicParagraphCreate(
                text=new_prediction.document, prediction=new_prediction.labels or None
            )
            datapublic_paragraph_create(paragraph, session=session)
        else:
            update = DataPublicParagraphUpdate(prediction=new_prediction.labels or None)
            datapublic_paragraph_update(update, session=session)

    return new_prediction


# MARK: Validate
@router.post("/validation", response_model=list[DocLabel] | None)
async def datapublic_get_paragraph_validation(
    text_request: TextRequest = Body(
        {"text": "Acusado: Ramiro Marrón DNI 34.555.666."}
    ),
    session: Session = Depends(get_session),
) -> list[DocLabel] | None:
    """
    Get the validation labels for a given paragraph text.
    """

    text = text_request.text
    paragraph_id = text_to_uuid(text)

    paragraph = datapublic_paragraph_read(paragraph_id, session=session)
    if not paragraph:
        return None

    return paragraph.validation


# MARK: Document Validation Save
@router.post("/validation/document/{document_id}")
async def datapublic_save_document_validation(
    document_id: UUID5,
    annotations: DocumentAnnotations,
    session: Session = Depends(get_session),
) -> DocumentInformation:
    logger.info(f"processing annotations => {document_id}")

    paragraphs = [
        DataPublicParagraph(
            id=text_to_uuid(paragraph.document),
            text=paragraph.document,
            validation=paragraph.labels or [],
        )
        for paragraph in annotations
    ]
    paragraphs = datapublic_paragraph_batch_create_update(paragraphs, session=session)

    datapublic_document_create(
        id=document_id,
        name=str(document_id),
        paragraphs=paragraphs,
        session=session,
        override=True,
    )
