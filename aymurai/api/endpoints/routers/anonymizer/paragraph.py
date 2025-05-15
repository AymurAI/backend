import os
from threading import Lock

import torch
from fastapi import Depends, Query, HTTPException
from fastapi.routing import APIRouter
from pydantic import UUID4
from sqlmodel import Session

from aymurai.api.utils import load_pipeline
from aymurai.api.endpoints.routers.anonymizer.core import get_anonimization_model
from aymurai.database.schema import (
    Document,
    Model,
    Prediction,
    PredictionCreate,
    Paragraph,
)
from aymurai.database.crud.prediction import read_prediction_by_text
from aymurai.database.session import get_session
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import (
    DocLabel,
    DocumentInformation,
)
from aymurai.settings import settings
from aymurai.utils.misc import get_element

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH
torch.set_num_threads(100)  # FIXME: polemic ?
pipeline_lock = Lock()


router = APIRouter()


# MARK: Paragraph Predict
@router.post("/paragraph/{paragraph_id}", response_model=DocumentInformation)
async def anonymizer_paragraph_predict(
    paragraph_id: UUID4,
    use_cache: bool = Query(
        True, description="Use cache to store or retrive predictions"
    ),
    session: Session = Depends(get_session),
    model: Model = Depends(get_anonimization_model),
) -> DocumentInformation:
    """
    Endpoint to predict anonymization for a given paragraph of text.

    Args:
        text_request (TextRequest): The request body containing the text to be anonymized.
        use_cache (bool): Flag to determine whether to use cache for storing or retrieving predictions.
        session (Session): Database session dependency.

    Returns:
        DocumentInformation: The anonymized document information including the text and labels.
    """

    paragraph = session.get(Paragraph, paragraph_id)
    if not paragraph:
        raise HTTPException(
            status_code=404,
            detail=f"Paragraph not found: {paragraph_id}",
        )
    input_text = paragraph.text

    logger.info(f"Running prediction: {model.name} ({model.version})")

    logger.info(f"Checking cache (use cache: {use_cache})")

    # —————— Check cache —————————————————————————————————————————————————————————————
    cached_pred = read_prediction_by_text(
        text=input_text, model_id=model.id, session=session
    )
    if cached_pred and use_cache:
        logger.info(f"cache loaded from prediction: {cached_pred.id}")
        logger.debug(f"{cached_pred}")

        labels = cached_pred.validation or cached_pred.prediction

        return DocumentInformation(document=cached_pred.input, labels=labels)

    # ——————— Run prediction —————————————————————————————————————————————————————————
    logger.info("Running prediction")
    item = [{"path": "empty", "data": {"doc.text": input_text}}]
    pipeline = load_pipeline(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "flair-anonymizer")
    )

    with pipeline_lock:
        processed = pipeline.preprocess(item)
        processed = pipeline.predict_single(processed[0])
        processed = pipeline.postprocess([processed])

    output_text = get_element(processed[0], ["data", "doc.text"]) or ""
    output_labels = get_element(processed[0], ["predictions", "entities"]) or []

    # ———————— Sanity check ——————————————————————————————————————————————————————————
    if input_text != output_text:
        logger.critical(
            f"Input and output text do not match: {input_text} != {output_text}"
        )
        if settings.ERROR_HANDLER == "raise":
            raise ValueError("Input and output text do not match")

    # Run validation on the output labels
    output_labels = [
        DocLabel(**label).model_dump(mode="json") for label in output_labels
    ]

    # ——————— Save to cache ——————————————————————————————————————————————————————————
    if cached_pred:
        logger.info(f"saving in cache: {cached_pred.id}")

        logger.warning(f"Prediction already exists: {cached_pred}. Updating.")
        cached_pred.input = output_text
        cached_pred.prediction = output_labels
    else:
        pred = PredictionCreate(
            input=output_text,
            prediction=output_labels,
            fk_model=model.id,
            fk_paragraph=paragraph.id,
        ).compile()

    session.add(cached_pred if cached_pred else pred)
    session.commit()
    session.refresh(pred)

    return DocumentInformation(document=pred.input, labels=pred.prediction)


# MARK: Paragraph Validate
@router.post("/paragraph/{paragraph_id}/validate")
async def anonymizer_save_document_validation(
    paragraph_id: UUID4,
    annotations: list[DocumentInformation],
    session: Session = Depends(get_session),
    model: Model = Depends(get_anonimization_model),
) -> list[DocLabel] | None:
    document = session.get(Document, paragraph_id)

    # ———————— Sanity check ——————————————————————————————————————————————————————————
    # Check if the document exists
    if not document:
        raise ValueError(f"Document not found: {paragraph_id}")

    # Check length of annotations and document match
    if len(annotations) != len(document.paragraphs):
        raise ValueError(
            f"The number of annotated paragraphs ({len(annotations)}) does not"
            f" match the number of paragraphs in the document"
            f" ({len(document.paragraphs)})"
        )

    # Check if the annotated paragraphs match the document paragraphs one by one
    for i, (annot_paragraph, doc_paragraph) in enumerate(
        zip(annotations, document.paragraphs)
    ):
        if annot_paragraph.document != doc_paragraph.text:
            msg = (
                f"The annotated paragraph ({annot_paragraph.document}) does not match"
                f" the document paragraph ({doc_paragraph.text})"
            )
            if settings.ERROR_HANDLER == "raise":
                raise ValueError(msg)
            logger.warning(msg)

    # ——————— Updating validations ———————————————————————————————————————————————————
    predictions = []
    for paragraph in annotations:
        prediction = read_prediction_by_text(
            text=paragraph.document, model_id=model.id, session=session
        )
        if prediction:
            prediction.validation = paragraph.labels
            predictions.append(prediction)
        else:
            logger.warning("Prediction not found.")
            if settings.ERROR_HANDLER == "raise":
                raise ValueError(
                    f"Prediction not found for paragraph: `{paragraph.document}`"
                )
            prediction = Prediction(
                input=paragraph.document,
                fk_model=model.id,
                validation=paragraph.labels,
            )
            predictions.append(prediction)

    session.add_all(predictions)
    session.commit()
    for prediction in predictions:
        session.refresh(prediction)

    return
