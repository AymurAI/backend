import os
import json
import tempfile
from threading import Lock
from subprocess import getoutput

import torch
from sqlmodel import Session
from fastapi.routing import APIRouter
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from fastapi import Body, Form, Depends, UploadFile

from aymurai.logger import get_logger
from aymurai.utils.misc import get_element
from aymurai.api.utils import load_pipeline
from aymurai.database.session import get_session
from aymurai.text.anonymization import DocAnonymizer
from aymurai.database.utils import data_to_uuid, text_to_uuid
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER
from aymurai.database.crud.anonymization.document import document_create
from aymurai.meta.api_interfaces import (
    DocLabel,
    TextRequest,
    DocumentAnnotations,
    DocumentInformation,
)
from aymurai.database.schema import (
    AnonymizationParagraph,
    AnonymizationParagraphCreate,
    AnonymizationParagraphUpdate,
)
from aymurai.database.crud.anonymization.paragraph import (
    paragraph_read,
    paragraph_create,
    paragraph_update,
    paragraph_batch_create_update,
)

logger = get_logger(__name__)


torch.set_num_threads = 100  # FIXME: polemic ?
pipeline_lock = Lock()


router = APIRouter()


# MARK: Predict
@router.post("/predict", response_model=DocumentInformation)
async def anonymizer_paragraph_predict(
    text_request: TextRequest = Body(
        {"text": "Acusado: Ramiro Marrón DNI 34.555.666."}
    ),
    use_cache: bool = True,
    session: Session = Depends(get_session),
) -> DocumentInformation:
    """
    Run the anonymizer model to a text

    Args:
        text_request (JSON, optional): JSON containing a "text" field. Defaults to Body({"text": "Acusado: Ramiro Marrón DNI 34.555.666."}).

    Returns:
        DocumentInformation: JSON containing the prediction
    """
    logger.info("anonymization predict single")

    logger.info(f"Checking cache (use cache: {use_cache})")
    text = text_request.text
    paragraph_id = text_to_uuid(text)

    cached_prediction = paragraph_read(paragraph_id, session=session)
    if cached_prediction and use_cache:
        logger.info(f"cache loaded from key: {paragraph_id}")
        logger.info(f"{cached_prediction}")
        return DocumentInformation(
            document=cached_prediction.text, labels=cached_prediction.prediction or []
        )

    logger.info("Running prediction")
    item = [{"path": "empty", "data": {"doc.text": text_request.text}}]
    pipeline = load_pipeline("/resources/pipelines/production/flair-anonymizer")

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
            paragraph = AnonymizationParagraphCreate(
                text=new_prediction.document, prediction=new_prediction.labels or None
            )
            paragraph_create(paragraph, session=session)
        else:
            update = AnonymizationParagraphUpdate(
                prediction=new_prediction.labels or None
            )
            paragraph_update(update, session=session)

    return new_prediction


# MARK: Validate
@router.post("/validation", response_model=list[DocLabel] | None)
async def anonymizer_get_paragraph_validation(
    text_request: TextRequest = Body(
        {"text": "Acusado: Ramiro Marrón DNI 34.555.666."}
    ),
    db: Session = Depends(get_session),
) -> list[DocLabel] | None:
    """
    Get the validation labels for a given paragraph text.
    """

    text = text_request.text
    paragraph_id = text_to_uuid(text)

    paragraph = paragraph_read(paragraph_id)
    if not paragraph:
        return None

    return paragraph.validation


# MARK: Document Compilation
@router.post("/anonymize-document")
async def anonymizer_compile_document(
    file: UploadFile,
    annotations: str = Form(...),
    session: Session = Depends(get_session),
) -> FileResponse:
    """
    Compile Anonimized document from original file and annotations

    Args:
        file (UploadFile): Original DOCX file
        annotations (str, optional): JSON with document annotations.

    Returns:
        FileResponse: Anonymized document
    """
    logger.info(f"receiving => {file.filename}")
    extension = MIMETYPE_EXTENSION_MAPPER.get(file.content_type)
    logger.info(f"detection extension: {extension} ({file.content_type})")

    tmp_filename = f"/tmp/{file.filename}"
    logger.info(f"saving temp file on local storage => {tmp_filename}")
    with open(tmp_filename, "wb") as tmp_file:
        data = file.file.read()
        tmp_file.write(data)
    logger.info(f"saved temp file on local storage => {tmp_filename}")

    annots = json.loads(annotations)
    annots = DocumentAnnotations(data=annots)
    logger.info(f"processing annotations => {annots}")

    # Add paragraphs to the database
    # validation MUST be at least an empty list, to remember user feedback
    paragraphs = [
        AnonymizationParagraph(
            id=text_to_uuid(paragraph.document),
            text=paragraph.document,
            validation=paragraph.labels or [],
        )
        for paragraph in annots.data
    ]
    paragraphs = paragraph_batch_create_update(paragraphs, session=session)

    document_create(
        id=data_to_uuid(data),
        name=file.filename,
        paragraphs=paragraphs,
        session=session,
        override=True,
    )

    # Anonymize the document
    doc_anonymizer = DocAnonymizer()

    item = {"path": tmp_filename}
    doc_anonymizer(
        item,
        [document_information.model_dump() for document_information in annots.data],
        "/tmp",
    )
    logger.info(f"saved temp file on local storage => {tmp_filename}")

    # Connvert to ODT
    with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".docx") as temp:
        with open(tmp_filename, "rb") as f:
            temp.write(f.read())

        temp.flush()

        cmd = "libreoffice --headless --convert-to odt --outdir /tmp {file}"
        getoutput(cmd.format(file=temp.name))
        odt = temp.name.replace(".docx", ".odt")

        os.remove(tmp_filename)

        return FileResponse(
            odt,
            background=BackgroundTask(os.remove, odt),
            media_type="application/octet-stream",
            filename=f"{os.path.splitext(os.path.basename(tmp_filename))[0]}.odt",
        )
