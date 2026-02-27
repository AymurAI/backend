import json
import os
import subprocess
import tempfile
from pathlib import Path
from threading import Lock
from typing import Literal, cast

from fastapi import Body, Depends, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from sqlmodel import Session
from starlette.background import BackgroundTask

from aymurai.api.endpoints.routers.anonymizer.utils import (
    PROCESSOR_MAP,
    SCORER_MAP,
    build_canonical_entities,
    resolve_processor,
)
from aymurai.api.exceptions.base import UnsupportedFileType
from aymurai.api.utils import load_pipeline
from aymurai.database.crud.anonymization.document import anonymization_document_create
from aymurai.database.crud.anonymization.paragraph import (
    anonymization_paragraph_batch_create_update,
    anonymization_paragraph_create,
    anonymization_paragraph_read,
)
from aymurai.database.schema import AnonymizationParagraph
from aymurai.database.session import get_session
from aymurai.database.utils import data_to_uuid, text_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import (
    ASRDocument,
    DocLabel,
    DocumentAnnotations,
    DocumentInformation,
    TextRequest,
)
from aymurai.meta.entities import CanonicalEntities
from aymurai.settings import settings
from aymurai.text.anonymization import DocAnonymizer
from aymurai.utils.cache import cache_load
from aymurai.utils.misc import get_element

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH
pipeline_lock = Lock()


router = APIRouter()


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

    logger.info("anonymization predict single")

    logger.info(f"Checking cache (use cache: {use_cache})")
    text = text_request.text
    paragraph_id = text_to_uuid(text)

    cached_prediction = session.get(AnonymizationParagraph, paragraph_id)
    if cached_prediction and use_cache:
        logger.info(f"cache loaded from key: {paragraph_id}")
        logger.debug(f"{cached_prediction}")

        labels = cached_prediction.prediction
        return DocumentInformation(document=cached_prediction.text, labels=labels or [])

    logger.info("Running prediction")
    item = [{"path": "empty", "data": {"doc.text": text_request.text}}]
    pipeline = load_pipeline(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "flair-anonymizer")
    )

    with pipeline_lock:
        processed = pipeline.preprocess(item)
        processed = pipeline.predict_single(processed[0])
        processed = pipeline.postprocess([processed])

    text = get_element(processed[0], ["data", "doc.text"]) or ""
    labels = get_element(processed[0], ["predictions", "entities"]) or []

    if use_cache:
        logger.info(f"saving in cache: {paragraph_id}")
        paragraph = AnonymizationParagraph(
            id=paragraph_id,
            text=text,
            prediction=labels,
        )
        paragraph = anonymization_paragraph_create(paragraph, session=session)

    return DocumentInformation(document=text, labels=paragraph.prediction)


@router.post("/disambiguate", response_model=CanonicalEntities)
async def anonymizer_disambiguate(
    paragraphs: list[DocumentInformation] = Body(
        ...,
        description=(
            "List of per-paragraph predictions returned by /anonymizer/predict."
        ),
    ),
    target_labels: list[str] | None = Query(
        None,
        description="Optional label filter, e.g. PER,DNI.",
    ),
    threshold: int = Query(
        70,
        description="Minimum similarity score (0-100) to cluster entities.",
    ),
    scorer: str = Query(
        "token_set_ratio",
        description="RapidFuzz scorer name for similarity.",
    ),
    processor: str = Query(
        "light_normalizer",
        description="Text processor to normalize before similarity.",
    ),
) -> CanonicalEntities:
    """
    Prototype endpoint for canonical entity grouping using fuzzy matching.
    """
    if threshold < 0 or threshold > 100:
        raise HTTPException(status_code=400, detail="threshold must be 0-100.")

    scorer_fn = SCORER_MAP.get(scorer.lower())
    if scorer_fn is None:
        raise HTTPException(status_code=400, detail=f"Unsupported scorer: {scorer}")

    if processor.lower() not in PROCESSOR_MAP:
        raise HTTPException(
            status_code=400, detail=f"Unsupported processor: {processor}"
        )
    processor_fn = resolve_processor(processor)

    labels = [label for paragraph in paragraphs for label in (paragraph.labels or [])]

    target_set = {label.strip() for label in target_labels} if target_labels else None
    canonical_entities = build_canonical_entities(
        labels,
        target_labels=target_set,
        threshold=threshold,
        scorer=scorer_fn,
        processor=processor_fn,
    )
    return CanonicalEntities(canonical_entities=canonical_entities)


# MARK: Validate
@router.post("/validation", response_model=list[DocLabel] | None)
async def anonymizer_get_paragraph_validation(
    text_request: TextRequest = Body(
        {"text": "Acusado: Ramiro Marrón DNI 34.555.666."}
    ),
    session: Session = Depends(get_session),
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
    paragraph_id = text_to_uuid(text)

    paragraph = anonymization_paragraph_read(paragraph_id, session=session)
    if not paragraph:
        return None

    return paragraph.validation


# MARK: Document Compilation
@router.post("/anonymize-document")
async def anonymizer_compile_document(
    file: UploadFile,
    annotations: str = Form(...),
    output_format: Literal["document", "audio"] = Form("document"),
    session: Session = Depends(get_session),
) -> FileResponse:
    """
    Compile Anonimized document from original file and annotations

    Args:
        file (UploadFile): Original file.
        annotations (str, optional): JSON with document annotations.

    Returns:
        FileResponse: Anonymized document
    """

    filename = Path(file.filename)
    logger.info(f"receiving => {filename.name}")

    data = file.file.read()
    extension = filename.suffix.lower().lstrip(".")

    annots_json = json.loads(annotations)
    annots = DocumentAnnotations.model_validate(annots_json)
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
    paragraphs = anonymization_paragraph_batch_create_update(
        paragraphs, session=session
    )

    anonymization_document_create(
        id=data_to_uuid(data),
        name=filename.name,
        paragraphs=paragraphs,
        session=session,
        override=False,
    )

    match extension:
        case "docx":
            tmp_filename = anonimize_docx(data, annots)
        case "pdf" | "odt" | "txt":
            tmp_filename = anonymize_document(data, annots)
        case "wav" | "mp3" | "m4a" | "flac" | "aac" | "ogg" | "opus":
            tmp_filename = anonimize_audio(data, annots)
        case _:
            raise UnsupportedFileType(
                detail=(
                    f"Unsupported file type {extension} for output format {output_format}."
                )
            )

    if not tmp_filename.exists():
        raise RuntimeError(f"Anonymized file not found at {tmp_filename}")

    # Convert to ODT
    tmp_dir = tempfile.gettempdir()
    cmd = [
        settings.LIBREOFFICE_BIN,
        "--headless",
        "--convert-to",
        "odt",
        "--outdir",
        tmp_dir,
        str(tmp_filename),
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

    odt = str(Path(tmp_filename).with_suffix(".odt"))
    logger.info(f"Expected output file path: {odt}")

    if not os.path.exists(odt):
        raise RuntimeError(f"File at path {odt} does not exist.")

    # Ensure the temporary file is deleted
    os.remove(tmp_filename)

    return FileResponse(
        odt,
        background=BackgroundTask(os.remove, odt),
        media_type="application/octet-stream",
        filename=f"{os.path.splitext(filename.name)[0]}.odt",
    )


def anonimize_audio(
    data: bytes,
    annotations: DocumentAnnotations,
) -> Path:
    doc_anonymizer = DocAnonymizer()

    document_id = data_to_uuid(data)
    document: ASRDocument = cast(ASRDocument, cache_load(str(document_id)))

    for asr_paragraph, paragraph_information in zip(
        document.document, annotations.data
    ):
        if asr_paragraph.text != paragraph_information.document:
            raise ValueError(
                "ASR paragraph text does not match annotation document:"
                f" {asr_paragraph.text} != {paragraph_information.document}"
            )
        asr_paragraph.text = (
            doc_anonymizer.replace_labels_in_text(paragraph_information.model_dump())
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )

    tmp_dir = tempfile.gettempdir()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, dir=tmp_dir) as f:
        tmp_filename = f.name
        logger.info(f"saving temp file on local storage => {tmp_filename}")
        f.write(document.to_txt().encode())

        # Add watermark to the end of the document
        f.write(
            "\n\nDocumento anonimizado por AymurAI\n\nhttps://www.aymurai.info/".encode()
        )

    return Path(tmp_filename)


def anonimize_docx(
    data: bytes,
    annotations: DocumentAnnotations,
    suffix: Literal["docx"] = "docx",
) -> Path:
    # Create a temporary file
    tmp_dir = tempfile.gettempdir()

    # Use delete=False to avoid the file being deleted when the NamedTemporaryFile object is closed
    # This is necessary on Windows, as the file is locked by the file object and cannot be deleted
    with tempfile.NamedTemporaryFile(
        suffix=f".{suffix}", delete=False, dir=tmp_dir
    ) as tmp_file:
        tmp_filename = tmp_file.name
        logger.info(f"saving temp file on local storage => {tmp_filename}")
        tmp_file.write(data)
        tmp_file.flush()
        tmp_file.close()

    logger.info(f"saved temp file on local storage => {tmp_filename}")

    # Anonymize the document
    doc_anonymizer = DocAnonymizer()

    item = {"path": tmp_filename}
    doc_anonymizer(
        item,
        [
            document_information.model_dump()
            for document_information in annotations.data
        ],
        tmp_dir,
    )
    logger.info(f"saved temp file on local storage => {tmp_filename}")

    return Path(tmp_filename)


def anonymize_document(annotations: DocumentAnnotations) -> Path:
    # Anonymize the document
    doc_anonymizer = DocAnonymizer()

    # Export as raw document
    anonymized_doc = [
        doc_anonymizer.replace_labels_in_text(document_information.model_dump())
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        for document_information in annotations.data
    ]

    tmp_dir = tempfile.gettempdir()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, dir=tmp_dir) as f:
        tmp_filename = f.name
        f.write("\n".join(anonymized_doc).encode())

        # Add watermark to the end of the document
        f.write(
            "\n\nDocumento anonimizado por AymurAI\n\nhttps://www.aymurai.info/".encode()
        )

    return Path(tmp_filename)
