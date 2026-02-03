import json
import os
import subprocess
import tempfile
from threading import Lock
from typing import Literal

import torch
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
    validate_canonical_entities,
    llm_canonical_entities_inference,
    map_canonical_entities_NER_preds,
    load_prompts_from_yaml,
)
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
    DocLabel,
    DocumentAnnotations,
    DocumentInformation,
    TextRequest,
    PromptLibrary,
)

from aymurai.settings import settings
from aymurai.text.anonymization import DocAnonymizer
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER
from aymurai.utils.misc import get_element

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH
torch.set_num_threads = 100  # FIXME: polemic ?
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


# MARK: Disambiguate
@router.post("/disambiguate", response_model=DocumentAnnotations)
async def anonymizer_disambiguate(
    paragraphs: list[DocumentInformation] = Body(
        ...,
        description=(
            "List of per-paragraph predictions returned by /anonymizer/predict."
        ),
    ),
    custom_prompts: PromptLibrary = Body(
        default_factory=PromptLibrary,
        description=(
            "Set of prompts, user and system, for each label if it is provided."
        ),
    ),
    target_labels: list[str]
    | None = Query(
        None,
        description="Optional label filter, e.g. PER,DNI.",
    ),
    mode: Literal["fuzzyregex", "llm"] = Query(
        "llm",
        description="Disambiguation mode: 'fuzzyregex' for fast clustering, 'llm' for AI refinement.",
    ),
) -> DocumentAnnotations:
    """
    Performs canonical entity disambiguation using fuzzy matching and LLM refinement.

    Args:
        paragraphs: A list of DocumentInformation objects containing the NER
            predictions per paragraph that need to be disambiguated.
        custom_prompts: A PromptLibrary object containing optional system and
            user prompts. If not provided, the service uses the default prompts
            configured in the environment.
        target_labels: An optional list of entity labels to filter the
            disambiguation process (e.g., ["PER", "DNI"]). If None, all
            detected labels are processed.
        mode: The operational mode for the endpoint. 'fuzzyregex' performs
            fast, distance-based clustering only, while 'llm' includes
            high-fidelity AI refinement and role curation.

    Returns:
        DocumentAnnotations: The original annotations enriched with
            'canonical_entity_id' and 'role' fields for each resolved mention.
    """

    scorer_fn = SCORER_MAP.get(settings.SCORER.lower())
    # if scorer_fn is None:
    #     raise HTTPException(status_code=400, detail=f"Unsupported scorer: {settings.SCORER}")

    # if settings.PROCESSOR.lower() not in PROCESSOR_MAP:
    #     raise HTTPException(
    #         status_code=400, detail=f"Unsupported processor: {settings.PROCESSOR}"
    #     )
    processor_fn = resolve_processor(settings.PROCESSOR)

    # if not settings.TOKENIZER_MODEL:
    #     raise HTTPException(status_code=400, detail="Tokenizer model cannot be empty.")

    labels = [label for paragraph in paragraphs for label in (paragraph.labels or [])]

    prompt_library = load_prompts_from_yaml()

    labels_to_process = (
        target_labels if target_labels else list(prompt_library.as_dict.keys())
    )

    canonical_entities = build_canonical_entities(
        labels,
        target_labels=set(labels_to_process),
        threshold=settings.THRESHOLD,
        scorer=scorer_fn,
        processor=processor_fn,
    )

    # --- FUZZYREGEX ONLY MODE ---
    if mode == "fuzzyregex":
        canonical_entities_val = validate_canonical_entities(
            canonical_entities_raw=canonical_entities
        )

        predictions_fuzzy = map_canonical_entities_NER_preds(
            predictions=paragraphs,
            canonical_entities=canonical_entities_val,
        )

        return DocumentAnnotations(data=predictions_fuzzy)

    # --- LLM REFINEMENT MODE ---
    canonical_entities_llm = []

    for label in labels_to_process:
        prompt_set = custom_prompts.get(label) or prompt_library.get(label)

        if (
            not prompt_set
            or not prompt_set.system.strip()
            or not prompt_set.user.strip()
        ):
            continue

        entities_for_this_label = validate_canonical_entities(
            canonical_entities_raw=canonical_entities, target_label=label
        )

        if not entities_for_this_label:
            continue

        llm_response = llm_canonical_entities_inference(
            paragraphs=paragraphs,
            canonical_entities_pre_cluster=entities_for_this_label,
            system_prompt=prompt_set.system,
            user_prompt_template=prompt_set.user,
            model=settings.MODEL,
            context_window_length=settings.CONTEXT_WINDOW_LENGTH,
            model_context=settings.MODEL_CONTEXT,
            token_limit_frac=settings.TOKEN_LIMIT_FRAC,
            tokenizer_model=settings.TOKENIZER_MODEL,
            target_label=label,
            temperature=settings.TEMPERATURE,
            decompose_by=settings.DECOMPOSE_BY,
        )

        if llm_response:
            canonical_entities_llm.extend(llm_response)

    predictions_llm = map_canonical_entities_NER_preds(
        predictions=paragraphs,
        canonical_entities=canonical_entities_llm,
    )

    return DocumentAnnotations(data=predictions_llm)


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
    logger.info(f"receiving => {file.filename}")
    extension = MIMETYPE_EXTENSION_MAPPER.get(file.content_type)
    logger.info(f"detection extension: {extension} ({file.content_type})")

    # Create a temporary file
    _, suffix = os.path.splitext(file.filename)
    suffix = suffix if suffix == ".docx" else ".txt"
    tmp_dir = tempfile.gettempdir()

    # Use delete=False to avoid the file being deleted when the NamedTemporaryFile object is closed
    # This is necessary on Windows, as the file is locked by the file object and cannot be deleted
    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False, dir=tmp_dir
    ) as tmp_file:
        tmp_filename = tmp_file.name
        logger.info(f"saving temp file on local storage => {tmp_filename}")
        data = file.file.read()
        tmp_file.write(data)
        tmp_file.flush()
        tmp_file.close()

    logger.info(f"saved temp file on local storage => {tmp_filename}")

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
        name=file.filename,
        paragraphs=paragraphs,
        session=session,
        override=False,
    )

    # Anonymize the document
    doc_anonymizer = DocAnonymizer()

    if suffix == ".docx":
        item = {"path": tmp_filename}
        doc_anonymizer(
            item,
            [document_information.model_dump() for document_information in annots.data],
            tmp_dir,
        )
        logger.info(f"saved temp file on local storage => {tmp_filename}")

    else:
        # Export as raw document
        anonymized_doc = [
            doc_anonymizer.replace_labels_in_text(document_information.model_dump())
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            for document_information in annots.data
        ]
        with open(tmp_filename, "w") as f:
            f.write("\n".join(anonymized_doc))

            # Add watermark to the end of the document
            f.write(
                "\n\nDocumento anonimizado por AymurAI\n\nhttps://www.aymurai.info/"
            )

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
        filename=f"{os.path.splitext(file.filename)[0]}.odt",
    )
