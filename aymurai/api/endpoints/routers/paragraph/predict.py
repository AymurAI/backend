import threading

from fastapi import Depends, HTTPException, Query
from fastapi.routing import APIRouter
from pydantic import UUID4
from sqlmodel import Session

from aymurai.api.utils import load_pipeline
from aymurai.database.crud.model import read_latest_model_by_type
from aymurai.database.crud.prediction import read_prediction_by_text
from aymurai.database.meta.extra import ParagraphPredictionPublic
from aymurai.database.schema import (
    ModelType,
    Paragraph,
    Prediction,
    PredictionCreate,
    PredictionPublic,
)
from aymurai.database.session import get_session
from aymurai.logger import get_logger
from aymurai.meta.entities import DocLabel
from aymurai.settings import settings
from aymurai.utils.misc import get_element

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH

prediction_lock = threading.Lock()

router = APIRouter()


# MARK: Paragraph Predict
@router.get(
    "/pipeline/{pipeline_type}/paragraph/{paragraph_id}/predict",
    response_model=ParagraphPredictionPublic,
)
async def paragraph_predict(
    paragraph_id: UUID4,
    pipeline_type: ModelType,
    use_cache: bool = Query(
        True, description="Use cache to store or retrieve predictions"
    ),
    session: Session = Depends(get_session),
) -> ParagraphPredictionPublic:
    """
    Endpoint to predict for a given paragraph of text.

    Args:
        paragraph_id (UUID4): The ID of the paragraph to be predicted.
        pipeline_type (ModelType): The type of model to be used for prediction.
        use_cache (bool): Flag to determine whether to use cache for storing or retrieving predictions.
        session (Session): Database session dependency.

    Returns:
        ParagraphPredictionPublic: The predicted document information including the text and labels.
    """
    model = read_latest_model_by_type(model_type=pipeline_type, session=session)
    pipeline = load_pipeline(model.pipeline_path)

    paragraph = session.get(Paragraph, paragraph_id)

    # ———————— Sanity check ——————————————————————————————————————————————————————————
    if not paragraph:
        raise HTTPException(
            status_code=404,
            detail=f"Paragraph not found: {paragraph_id}",
        )

    logger.info(f"Running prediction: {model.name} ({model.version})")

    input_text = paragraph.text
    # —————— Check cache —————————————————————————————————————————————————————————————
    logger.info(f"Checking cache (use cache: {use_cache})")
    cached_pred = read_prediction_by_text(
        text=input_text, model_id=model.id, session=session
    )
    if cached_pred and use_cache:
        logger.info(f"cache loaded from prediction: {cached_pred.id}")
        logger.debug(f"{cached_pred}")

        # Explicitly pass required fields to ParagraphPredictionPublic
        return ParagraphPredictionPublic(
            id=paragraph.id,
            text=paragraph.text,
            hash=paragraph.hash,
            index=paragraph.index,
            created_at=paragraph.created_at,
            updated_at=paragraph.updated_at,
            prediction=PredictionPublic(
                **cached_pred.model_dump(),
                model=cached_pred.model.model_dump(),
            ),
        )

    # ——————— Run prediction —————————————————————————————————————————————————————————
    logger.info("Running prediction")
    item = [{"path": "empty", "data": {"doc.text": input_text}}]

    with prediction_lock:
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
    if pred := cached_pred:
        logger.info(f"saving in cache: {pred.id}")

        logger.warning(f"Prediction already exists: {pred}. Updating.")
        pred.input = output_text
        pred.prediction = output_labels
    else:
        pred = PredictionCreate(
            input=output_text,
            prediction=output_labels,
            validation=None,
            fk_model=model.id,
            fk_paragraph=paragraph.id,
        ).compile()

    session.add(pred)
    session.commit()
    session.refresh(pred)

    return ParagraphPredictionPublic(
        id=paragraph.id,
        text=paragraph.text,
        index=paragraph.index,
        hash=paragraph.hash,
        created_at=paragraph.created_at,
        updated_at=paragraph.updated_at,
        prediction=PredictionPublic(
            **pred.model_dump(),
            model=pred.model.model_dump(),
        ),
    )


# MARK: Paragraph Validate
@router.patch("/pipeline/{pipeline_type}/paragraph/{paragraph_id}/validate")
async def save_paragraph_validation(
    paragraph_id: UUID4,
    pipeline_type: ModelType,
    labels: list[DocLabel],
    session: Session = Depends(get_session),
) -> None:
    paragraph = session.get(Paragraph, paragraph_id)

    model = read_latest_model_by_type(model_type=pipeline_type, session=session)

    # ———————— Sanity check ——————————————————————————————————————————————————————————
    # Check if the document exists
    if not paragraph:
        raise HTTPException(
            status_code=404,
            detail=f"Paragraph not found: {paragraph_id}",
        )

    # ——————— Updating validations ———————————————————————————————————————————————————
    prediction = read_prediction_by_text(
        text=paragraph.text, model_id=model.id, session=session
    )
    if prediction:
        prediction.validation = labels
    else:
        logger.warning("Prediction not found.")
        if settings.ERROR_HANDLER == "raise":
            raise ValueError(f"Prediction not found for paragraph: `{paragraph.id}`")
        prediction = Prediction(
            input=paragraph.text,
            fk_model=model.id,
            validation=labels,
        )

    session.add(prediction)
    session.commit()

    return
