import os
from threading import Lock

import torch
from fastapi import Body, Depends, Query, HTTPException
from fastapi.routing import APIRouter
from pydantic import UUID5
from sqlmodel import Session

from aymurai.api.utils import load_pipeline
from aymurai.database.schema import (
    DataPublicParagraph,
    DataPublicDocument,
    DataPublicDocumentParagraph,
)
from aymurai.database.session import get_session
from aymurai.database.utils import text_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import (
    DataPublicDocumentAnnotations,
    DocumentInformation,
    TextRequest,
)
from aymurai.settings import settings
from aymurai.utils.misc import get_element

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH
torch.set_num_threads = 100  # FIXME: polemic ?
pipeline_lock = Lock()


router = APIRouter()


# MARK: Predict
@router.post("/predict/{document_id}", response_model=DocumentInformation)
async def predict_over_text(
    document_id: UUID5,
    text_request: TextRequest = Body({"text": "Buenos Aires, 17 de noviembre 2024"}),
    use_cache: bool = Query(
        True, description="Use cache to store or retrive predictions"
    ),
    session: Session = Depends(get_session),
) -> DocumentInformation:
    logger.info("datapublic predict single")

    logger.info(f"Checking cache (use cache: {use_cache})")
    text = text_request.text
    paragraph_id = text_to_uuid(text)

    cached_prediction = session.get(DataPublicParagraph, paragraph_id)
    if cached_prediction and use_cache:
        logger.info(f"cache loaded from key: {paragraph_id}")
        logger.debug(f"{cached_prediction}")
        labels = cached_prediction.prediction
        return DocumentInformation(document=cached_prediction.text, labels=labels or [])

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

    text = get_element(processed[0], ["data", "doc.text"]) or ""
    labels = get_element(processed[0], ["predictions", "entities"]) or []

    if use_cache:
        logger.info(f"saving in cache: {paragraph_id}")

        document = session.get(DataPublicDocument, document_id)
        if not document:
            document = DataPublicDocument(id=document_id)

        paragraph = DataPublicParagraph(id=paragraph_id, text=text, prediction=labels)
        document_paragraphs = DataPublicDocumentParagraph(
            paragraph_id=paragraph_id,
            document_id=document_id,
        )

        session.add_all([document, paragraph, document_paragraphs])
        session.commit()
        session.refresh(paragraph)

        # paragraph = datapublic_paragraph_create(paragraph, session=session)

    return DocumentInformation(document=text, labels=paragraph.prediction)


# MARK: Validate Paragraph
# @router.post("/validation", response_model=list[DocLabel] | None)
# async def datapublic_get_paragraph_validation(
#     text_request: TextRequest = Body(
#         {"text": "Acusado: Ramiro Marrón DNI 34.555.666."}
#     ),
#     session: Session = Depends(get_session),
# ) -> list[DocLabel] | None:
#     """
#     Get the validation labels for a given paragraph text.
#     """

#     text = text_request.text
#     paragraph_id = text_to_uuid(text)

#     paragraph = datapublic_paragraph_read(paragraph_id, session=session)
#     if not paragraph:
#         return None

#     return paragraph.validation


# MARK: GET Validation Document
@router.get("/validation/document/{document_id}")
async def datapublic_read_document_validation(
    document_id: UUID5,
    session: Session = Depends(get_session),
) -> DataPublicDocumentAnnotations | None:
    logger.info(f"loading annotations => {document_id}")

    document = session.get(DataPublicDocument, document_id)
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id}",
        )

    annotations = document.validation
    if not annotations:
        return None

    return DataPublicDocumentAnnotations(root=annotations)


# MARK: POST Validation Document
@router.post("/validation/document/{document_id}")
async def datapublic_save_document_validation(
    document_id: UUID5,
    annotations: DataPublicDocumentAnnotations = Body(..., example={}),
    session: Session = Depends(get_session),
) -> None:
    logger.info(f"processing annotations => {document_id}")

    document = session.get(DataPublicDocument, document_id)
    if not document:
        document = DataPublicDocument(id=document_id)

    document.validation = annotations.root
    session.add(document)
    session.commit()
    session.refresh(document)
    logger.info(f"document validation saved => {document_id}")

    return
