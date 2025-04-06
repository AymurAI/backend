import os
import subprocess
import tempfile
from functools import cache
from threading import Lock

import torch
from fastapi import Body, Depends, Query
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from pydantic import UUID5
from sqlmodel import Session
from starlette.background import BackgroundTask

from aymurai.api.utils import load_pipeline
from aymurai.database.crud.model import register_model
from aymurai.database.crud.prediction import read_prediction, read_validation
from aymurai.database.schema import (
    Document,
    Model,
    Prediction,
    PredictionCreate,
)
from aymurai.database.session import get_session
from aymurai.database.utils import text_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import (
    DocLabel,
    DocumentInformation,
    TextRequest,
)
from aymurai.settings import settings
from aymurai.text.anonymization import DocAnonymizer
from aymurai.utils.misc import get_element

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH
torch.set_num_threads = 100  # FIXME: polemic ?
pipeline_lock = Lock()


router = APIRouter()


@cache
def get_model(session: Session = Depends(get_session)) -> Model:
    """
    Get the model from the database.

    Args:
        session (Session): Database session dependency.

    Returns:
        Model: The model from the database.
    """
    return register_model(
        model_name="flair-anonymizer",
        app_version=settings.APP_VERSION,
        session=session,
    )


# MARK: Predict
@router.post("/predict", response_model=DocumentInformation)
async def anonymizer_paragraph_predict(
    text_request: TextRequest = Body(
        {"text": "Acusado: Ramiro Marrón DNI 34.555.666."}
    ),
    use_cache: bool = Query(
        True, description="Use cache to store or retrive predictions"
    ),
    session: Session = Depends(get_session),
    model: Model = Depends(get_model),
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

    logger.info(f"Running prediction: {model.name} ({model.version})")

    logger.info(f"Checking cache (use cache: {use_cache})")
    input_text = text_request.text
    prediction_id = text_to_uuid(f"{input_text}-{model.id}")

    ##################################################################################
    # Load from cache
    ##################################################################################
    cached_prediction = read_prediction(
        text=input_text, model_id=model.id, session=session
    )
    if cached_prediction and use_cache:
        logger.info(f"cache loaded from prediction: {cached_prediction.id}")
        logger.debug(f"{cached_prediction}")

        return DocumentInformation(
            document=cached_prediction.input, labels=cached_prediction.prediction
        )

    ##################################################################################
    # Predict
    ##################################################################################

    logger.info("Running prediction")
    item = [{"path": "empty", "data": {"doc.text": text_request.text}}]
    pipeline = load_pipeline(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "flair-anonymizer")
    )

    with pipeline_lock:
        processed = pipeline.preprocess(item)
        processed = pipeline.predict_single(processed[0])
        processed = pipeline.postprocess([processed])

    output_text = get_element(processed[0], ["data", "doc.text"]) or ""
    output_labels = get_element(processed[0], ["predictions", "entities"]) or []

    ##################################################################################
    # Sanity check
    ##################################################################################
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

    #################################################################################
    # Save to cache
    #################################################################################
    logger.info(f"saving in cache: {prediction_id}")
    pred = session.get(Prediction, prediction_id)
    if pred:
        logger.warning(f"Prediction already exists: {prediction_id}. Updating.")
        pred.input = output_text
        pred.prediction = output_labels
    else:
        pred = PredictionCreate(
            input=output_text,
            prediction=output_labels,
            fk_model=model.id,
        ).compile()

    session.add(pred)
    session.commit()
    session.refresh(pred)

    return DocumentInformation(document=pred.input, labels=pred.prediction)


# MARK: Validate
@router.post("/validation", response_model=list[DocLabel] | None)
async def anonymizer_get_paragraph_validation(
    text_request: TextRequest = Body(
        {"text": "Acusado: Ramiro Marrón DNI 34.555.666."}
    ),
    session: Session = Depends(get_session),
    model: Model = Depends(get_model),
) -> list[DocLabel] | None:
    """
    Get the validation labels for a given paragraph text.

    Args:
        text_request (TextRequest): The request body containing the text to be validated.
        session (Session): Database session dependency.

    Returns:
        list[DocLabel] | None: A list of validation labels for the given paragraph text, or None if no validation exists.
    """

    text = text_request.text

    logger.info(f"Checking validation: {model.name} ({model.version})")
    pred = read_validation(input_hash=text, model_name=model.name, session=session)

    if not pred:
        return None

    return pred.validation


# MARK: Document Compilation
@router.post("/anonymize-document")
async def anonymizer_compile_document(
    document_id: UUID5,
    annotations: list[DocumentInformation],
    session: Session = Depends(get_session),
    model: Model = Depends(get_model),
) -> FileResponse:
    """
    Compile Anonimized document from original file and annotations

    Args:
        file (UploadFile): Original file.
        annotations (str, optional): JSON with document annotations.

    Returns:
        FileResponse: Anonymized document
    """

    document = session.get(Document, document_id)

    ##################################################################################
    # Sanity check
    ##################################################################################
    # Check if the document exists
    if not document:
        raise ValueError(f"Document not found: {document_id}")

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

    ####################################################################################
    # Updating validations
    # ####################################################################################

    predictions = []
    for paragraph in annotations:
        with session.no_autoflush:
            prediction = read_prediction(
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

    ####################################################################################
    # Create a temporary file
    ####################################################################################

    filename = document.name
    logger.info(f"Document found: {document_id} ({filename})")

    # Create a temporary file
    _, suffix = os.path.splitext(filename)
    suffix = suffix if suffix == ".docx" else ".txt"
    tmp_dir = tempfile.gettempdir()

    # Use delete=False to avoid the file being deleted when the NamedTemporaryFile object is closed
    # This is necessary on Windows, as the file is locked by the file object and cannot be deleted
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=tmp_dir) as file:
        tmp_filename = file.name
        logger.info(f"saving temp file on local storage => {tmp_filename}")
        file.write(document.data)
        file.flush()
        file.close()

    logger.info(f"saved temp file on local storage => {tmp_filename}")

    ####################################################################################
    # Anonymize the document
    ####################################################################################
    doc_anonymizer = DocAnonymizer()

    if suffix == ".docx":
        item = {"path": tmp_filename}
        doc_anonymizer(
            item,
            [document_information.model_dump() for document_information in annotations],
            tmp_dir,
        )
        logger.info(f"saved temp file on local storage => {tmp_filename}")

    else:
        # Export as raw document
        anonymized_doc = [
            doc_anonymizer.replace_labels_in_text(document_information.model_dump())
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            for document_information in annotations
        ]
        with open(tmp_filename, "w") as f:
            f.write("\n".join(anonymized_doc))

    # Convert to ODT
    cmd = [
        settings.LIBREOFFICE_BIN,
        "--headless",
        "--convert-to",
        "odt",
        "--outdir",
        tmp_dir,
        tmp_filename,
    ]

    logger.info(f"Executing: {' '.join(cmd)}")

    try:
        output = subprocess.check_output(
            cmd, shell=False, encoding="utf-8", errors="ignore"
        )
        logger.info(f"LibreOffice output: {output}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"LibreOffice conversion failed: {e.output.decode('utf-8', errors='ignore')}"
        )

    odt = tmp_filename.replace(suffix, ".odt")
    logger.info(f"Expected output file path: {odt}")

    if not os.path.exists(odt):
        raise RuntimeError(f"File at path {odt} does not exist.")

    # Ensure the temporary file is deleted
    os.remove(tmp_filename)

    return FileResponse(
        odt,
        background=BackgroundTask(os.remove, odt),
        media_type="application/octet-stream",
        filename=f"{os.path.splitext(filename)[0]}.odt",
    )
