import json
import os
import subprocess
import tempfile
from pathlib import Path
from threading import Lock
from typing import Literal, cast

from fastapi import Body, Depends, Form, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from sqlmodel import Session
from starlette.background import BackgroundTask

from aymurai.api.exceptions.base import UnsupportedFileType
from aymurai.api.utils import load_pipeline
from aymurai.database.crud.anonymization.document import anonymization_document_create
from aymurai.database.crud.anonymization.paragraph import (
    anonymization_paragraph_batch_create_update,
    anonymization_paragraph_create,
    anonymization_paragraph_read,
)
from aymurai.database.schema import AnonymizationParagraph, AnonymizationParagraphCreate
from aymurai.database.session import get_session
from aymurai.database.utils import data_to_uuid, text_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import (
    ASRDocument,
    DocLabel,
    DocumentAnnotations,
    DocumentInformation,
    LabelPolicy,
    PromptLibrary,
    RenderPolicy,
    TextRequest,
)
from aymurai.settings import settings
from aymurai.text.anonymization import DocAnonymizer, replace_labels_in_text
from aymurai.utils.entity_disambiguation import (
    build_canonical_entities,
    get_canonical_dates,
    llm_canonical_entities_inference,
    load_prompts_from_yaml,
    map_canonical_entities_ner_preds,
)
from aymurai.utils.cache import cache_load
from aymurai.utils.misc import get_element

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH
pipeline_lock = Lock()


router = APIRouter()


def _entities_to_doclabels(entities: list[dict]) -> list[DocLabel]:
    """
    Convert raw entities to DocLabel objects.

    Args:
        entities (list[dict]): List of entity dictionaries.

    Returns:
        list[DocLabel]: List of DocLabel objects.
    """
    doclabels: list[DocLabel] = []

    for ent in entities:
        try:
            doclabels.append(
                DocLabel.model_validate(
                    {
                        "text": ent.get("text", ""),
                        "start_char": ent.get("start_char"),
                        "end_char": ent.get("end_char"),
                        "attrs": ent.get("attrs", {}),
                    }
                )
            )
        except Exception as exc:  # keep going if a single entity is malformed
            logger.warning(f"Skipping invalid entity for DocLabel: {exc}")

    return doclabels


def _merge_label_policies(
    request_policies: dict[str, LabelPolicy] | None,
) -> dict[str, LabelPolicy]:
    """
    Merges label policies from settings and request, with request policies taking precedence.

    Args:
        request_policies (dict[str, LabelPolicy] | None): Per-label policies provided in the request body.

    Returns:
        dict[str, LabelPolicy]: Effective per-label policies after merging settings and request policies.
    """
    policies: dict[str, LabelPolicy] = {}

    if settings.DISAMBIGUATION_LABEL_POLICIES:
        for label, policy in settings.DISAMBIGUATION_LABEL_POLICIES.items():
            incoming = LabelPolicy.model_validate(policy)
            current = policies.get(label, LabelPolicy())
            if incoming.disambiguation is not None:
                current.disambiguation = incoming.disambiguation
            if incoming.anonymize is not None:
                current.anonymize = incoming.anonymize
            if incoming.use_subclass_when_available is not None:
                current.use_subclass_when_available = (
                    incoming.use_subclass_when_available
                )
            policies[label] = current

    if request_policies:
        for label, policy in request_policies.items():
            incoming = LabelPolicy.model_validate(policy)
            current = policies.get(label, LabelPolicy())
            if incoming.disambiguation is not None:
                current.disambiguation = incoming.disambiguation
            if incoming.anonymize is not None:
                current.anonymize = incoming.anonymize
            if incoming.use_subclass_when_available is not None:
                current.use_subclass_when_available = (
                    incoming.use_subclass_when_available
                )
            policies[label] = current

    return policies


def _merge_render_policy(
    request_policy: RenderPolicy | None,
) -> RenderPolicy:
    """
    Merges render policies from settings and request, with request policy taking precedence.

    Args:
        request_policy (RenderPolicy | None): Render policy from request.

    Returns:
        RenderPolicy: Effective render policy.
    """
    policy = RenderPolicy(
        suffix_mode="auto",
        suffix_threshold=1,
    )

    def apply(incoming: RenderPolicy) -> None:
        nonlocal policy
        if incoming.suffix_mode is not None:
            policy.suffix_mode = incoming.suffix_mode
        if incoming.suffix_threshold is not None:
            policy.suffix_threshold = incoming.suffix_threshold

    if settings.RENDER_POLICY:
        apply(RenderPolicy.model_validate(settings.RENDER_POLICY))

    if request_policy:
        apply(RenderPolicy.model_validate(request_policy))

    return policy


def _resolve_token_base(
    label: DocLabel,
    label_policy: LabelPolicy,
) -> str:
    """
    Resolves the base token label for rendering.

    Args:
        label (DocLabel): Label to render.
        label_policy (LabelPolicy): Label policy rules.

    Returns:
        str: Base token label (e.g., PER, DENUNCIANTE).
    """
    attrs = label.attrs
    if attrs is None:
        return label.text

    subclass = None
    if attrs.aymurai_label_subclass:
        subclass = attrs.aymurai_label_subclass[0]

    if label_policy.use_subclass_when_available and subclass:
        return subclass.upper()

    return attrs.aymurai_label


def _build_render_context(
    annotations: list[DocumentInformation],
    render_policy: RenderPolicy,
    label_policies: dict[str, LabelPolicy],
) -> dict:
    """
    Builds render context with per-entity indices and counts.

    Args:
        annotations (list[DocumentInformation]): Document annotations.
        render_policy (RenderPolicy): Render policy rules.
        label_policies (dict[str, LabelPolicy]): Per-label policies.

    Returns:
        dict: Render context with policy, indices, and counts.
    """
    occurrences: list[tuple[int, int, str, str]] = []

    for p_idx, paragraph in enumerate(annotations):
        for label in paragraph.labels or []:
            label_policy = label_policies.get(
                label.attrs.aymurai_label
                if label.attrs and label.attrs.aymurai_label
                else None,
                LabelPolicy(),
            )
            base = _resolve_token_base(label, label_policy)
            entity_id = (
                str(label.attrs.canonical_entity_id)
                if label.attrs and label.attrs.canonical_entity_id
                else label.text
            )
            occurrences.append((p_idx, label.start_char, base, entity_id))

    occurrences.sort(key=lambda item: (item[0], item[1]))

    index_by_entity: dict[tuple[str, str], int] = {}
    next_index_by_base: dict[str, int] = {}

    for _, _, base, entity_id in occurrences:
        key = (base, entity_id)
        if key not in index_by_entity:
            next_index_by_base[base] = next_index_by_base.get(base, 0) + 1
            index_by_entity[key] = next_index_by_base[base]

    count_by_base = {base: count for base, count in next_index_by_base.items()}

    return {
        "render_policy": render_policy,
        "label_policies": label_policies,
        "index_by_entity": index_by_entity,
        "count_by_base": count_by_base,
    }


def _should_anonymize_label(
    label: DocLabel,
    label_policies: dict[str, LabelPolicy],
) -> bool:
    """
    Determines whether a given label should be anonymized based on its attributes and the effective label policies.

    Args:
        label (DocLabel): The document label to evaluate for anonymization.
        label_policies (dict[str, LabelPolicy]): Effective per-label policies that may override default anonymization behavior.

    Returns:
        bool: True if the label should be anonymized, False otherwise.
    """
    if label.attrs and label.attrs.aymurai_anonymize is not None:
        return bool(label.attrs.aymurai_anonymize)

    policy = (
        label_policies.get(str(label.attrs.aymurai_label).strip().upper())
        if label.attrs and label.attrs.aymurai_label
        else None
    )
    if policy is None:
        return True

    if policy.anonymize is None:
        return True

    return bool(policy.anonymize)


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

        labels = _entities_to_doclabels(cached_prediction.prediction or [])
        return DocumentInformation(document=cached_prediction.text, labels=labels)

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
    raw_entities = get_element(processed[0], ["predictions", "entities"]) or []
    labels = _entities_to_doclabels(raw_entities)

    if use_cache:
        logger.info(f"saving in cache: {paragraph_id}")
        paragraph = AnonymizationParagraphCreate(
            text=text,
            prediction=labels,
        )
        paragraph = anonymization_paragraph_create(paragraph, session=session)

    return DocumentInformation(document=text, labels=labels)


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
    label_policies: dict[str, LabelPolicy] | None = Body(
        None,
        description=(
            "Optional per-label policy overrides for disambiguation/anonymization."
        ),
    ),
    target_labels: list[str] | None = Query(
        None,
        description=(
            "Optional label filter for LLM refinement (e.g., PER,DNI). "
            "Fuzzy clustering still runs across all detected labels."
        ),
    ),
    session: Session = Depends(get_session),
) -> DocumentAnnotations:
    """
    Performs canonical entity disambiguation using fuzzy matching and LLM refinement.

    Args:
        paragraphs: A list of DocumentInformation objects containing the NER
            predictions per paragraph that need to be disambiguated.
        custom_prompts: A PromptLibrary object containing optional system and
            user prompts. If not provided, the service uses the default prompts
            configured in the environment.
        label_policies: Optional per-label disambiguation/anonymization policies.
        target_labels: An optional list of entity labels to refine via LLM
            (e.g., ["PER", "DNI"]). Fuzzy clustering still runs across all
            detected labels.
    Returns:
        DocumentAnnotations: The original annotations enriched with
            'canonical_entity_id' and 'role' fields for each resolved mention.
    """
    logger.info(
        "disambiguation start: paragraphs=%d",
        len(paragraphs),
    )

    labels = [label for paragraph in paragraphs for label in (paragraph.labels or [])]
    effective_label_policies = _merge_label_policies(label_policies)
    logger.info("disambiguation labels: %d", len(labels))

    prompt_library = load_prompts_from_yaml()

    all_detected_labels = {
        label.attrs.aymurai_label
        for label in labels
        if label.attrs
        and label.attrs.aymurai_label
        and effective_label_policies.get(label.attrs.aymurai_label)
        and effective_label_policies.get(label.attrs.aymurai_label).anonymize
    }

    default_llm_labels = (
        target_labels if target_labels else list(prompt_library.as_dict.keys())
    )

    llm_labels: list[str] = []
    fuzzy_labels: set[str] = set()

    for label in all_detected_labels:
        policy = effective_label_policies.get(label)
        if policy and policy.disambiguation == "llm":
            llm_labels.append(label)
            fuzzy_labels.add(label)
            continue
        if policy and policy.disambiguation == "fuzzy":
            fuzzy_labels.add(label)
            continue
        if policy and policy.disambiguation == "none":
            continue

        if label in default_llm_labels:
            llm_labels.append(label)
            fuzzy_labels.add(label)
        else:
            fuzzy_labels.add(label)

    effective_disambiguation_by_label: dict[str, str] = {}
    for label in all_detected_labels:
        if label in llm_labels:
            effective_disambiguation_by_label[label] = "llm"
        elif label in fuzzy_labels:
            effective_disambiguation_by_label[label] = "fuzzy"
        else:
            effective_disambiguation_by_label[label] = "none"
    logger.info(
        "disambiguation targets: detected=%s llm=%s",
        sorted(all_detected_labels),
        llm_labels,
    )

    canonical_entities = (
        build_canonical_entities(
            labels,
            target_labels=[label for label in fuzzy_labels if label != "FECHA"]
            if fuzzy_labels
            else None,
            threshold=settings.THRESHOLD,
        )
        if fuzzy_labels
        else []
    )

    if "FECHA" in fuzzy_labels:
        canonical_entities += get_canonical_dates(labels)

    logger.info(
        "fuzzy clustering produced %d canonical entities", len(canonical_entities)
    )

    # --- LLM REFINEMENT (policy-driven) ---
    canonical_entities_llm = []

    for label in llm_labels:
        logger.info("llm refinement: label=%s", label)
        prompt_set = custom_prompts.get(label) or prompt_library.get(label)

        if (
            not prompt_set
            or not prompt_set.system.strip()
            or not prompt_set.user.strip()
        ):
            logger.info("llm refinement skipped: missing prompt for label=%s", label)
            continue

        entities_for_this_label = [
            e for e in canonical_entities if e.aymurai_label == label
        ]

        if not entities_for_this_label:
            logger.info("llm refinement skipped: no entities for label=%s", label)
            continue
        logger.info(
            "llm refinement input: label=%s entities=%d",
            label,
            len(entities_for_this_label),
        )

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
            logger.info(
                "llm refinement output: label=%s entities=%d",
                label,
                len(llm_response),
            )

    canonical_entities_merged = canonical_entities_llm + [
        ce for ce in canonical_entities if ce.aymurai_label not in set(llm_labels)
    ]
    logger.info(
        "disambiguation merge: llm=%d fuzzy_only=%d total=%d",
        len(canonical_entities_llm),
        len(canonical_entities_merged) - len(canonical_entities_llm),
        len(canonical_entities_merged),
    )

    predictions = map_canonical_entities_ner_preds(
        predictions=paragraphs,
        canonical_entities=canonical_entities_merged,
        force_labels=set(llm_labels),
    )

    for document in predictions:
        for label in document.labels or []:
            label.attrs.aymurai_disambiguation = effective_disambiguation_by_label.get(
                label.attrs.aymurai_label, "fuzzy"
            )

            policy = effective_label_policies.get(label.attrs.aymurai_label)
            label.attrs.aymurai_anonymize = (
                policy.anonymize if policy and policy.anonymize is not None else True
            )

    paragraph_updates = [
        AnonymizationParagraphCreate(
            text=paragraph.document,
            prediction=paragraph.labels or [],
        )
        for paragraph in predictions
    ]
    anonymization_paragraph_batch_create_update(paragraph_updates, session=session)
    logger.info(
        "disambiguation persisted predictions for %d paragraphs",
        len(paragraph_updates),
    )

    return DocumentAnnotations(
        data=predictions,
        label_policies=effective_label_policies if effective_label_policies else None,
    )


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
    Anonymizes a document (text or audio) based on provided annotations and returns the anonymized file.

    Args:
        file (UploadFile): The uploaded file to be anonymized.
        annotations (str, optional): A JSON string representing the document annotations. Defaults to Form(...).
        output_format (Literal["document", "audio"], optional): The desired output format of the anonymized file. Defaults to Form("document").
        session (Session, optional): Database session dependency. Defaults to Depends(get_session).

    Raises:
        UnsupportedFileType: If the file type is not supported for anonymization.
        RuntimeError: If the anonymized file cannot be found.

    Returns:
        FileResponse: A response containing the anonymized file for download, with appropriate media type and filename.
    """
    filename = Path(file.filename)
    logger.info(f"receiving => {filename.name}")

    data = file.file.read()
    extension = filename.suffix.lower().lstrip(".")

    annots_json = json.loads(annotations)
    annots = DocumentAnnotations.model_validate(annots_json)
    logger.info(f"processing annotations => {annots}")
    effective_label_policies = _merge_label_policies(annots.label_policies)
    effective_render_policy = _merge_render_policy(annots.render_policy)

    # Add paragraphs to the database
    # validation MUST be at least an empty list, to remember user feedback
    paragraphs = [
        AnonymizationParagraphCreate(
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

    filtered_annotations = []
    for paragraph in annots.data:
        filtered_labels = [
            label
            for label in (paragraph.labels or [])
            if _should_anonymize_label(label, effective_label_policies)
        ]
        filtered_annotations.append(
            DocumentInformation(
                document=paragraph.document,
                labels=filtered_labels,
            )
        )

    filtered_annots = DocumentAnnotations(data=filtered_annotations)
    render_context = _build_render_context(
        filtered_annotations,
        effective_render_policy,
        effective_label_policies,
    )

    match extension:
        case "docx":
            tmp_filename = anonimize_docx(
                data,
                filtered_annots,
                render_context=render_context,
            )
        case "pdf" | "odt" | "txt":
            tmp_filename = anonymize_document(
                filtered_annots,
                render_context=render_context,
            )
        case "wav" | "mp3" | "m4a" | "flac" | "aac" | "ogg" | "opus":
            tmp_filename = anonimize_audio(
                data,
                filtered_annots,
                render_context=render_context,
            )
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
    render_context: dict | None = None,
) -> Path:
    """
    Anonymizes an audio document based on provided annotations and returns the path to the anonymized file.

    Args:
        data (bytes): The raw audio data to be anonymized.
        annotations (DocumentAnnotations): The document annotations containing the information needed for anonymization.
        render_context (dict | None, optional): Context for rendering the anonymized content, such as label policies and indices. Defaults to None.

    Raises:
        ValueError: If the ASR paragraph text does not match the annotation document.

    Returns:
        Path: The file path to the anonymized audio document.
    """
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
            replace_labels_in_text(
                paragraph_information.model_dump(),
                render_context=render_context,
            )
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
    render_context: dict | None = None,
) -> Path:
    """
    Anonymizes a DOCX document based on provided annotations and returns the path to the anonymized file.

    Args:
        data (bytes): The raw DOCX data to be anonymized.
        annotations (DocumentAnnotations): The document annotations containing the information needed for anonymization.
        suffix (Literal["docx"], optional): The file suffix for the temporary file. Defaults to "docx".
        render_context (dict | None, optional): Context for rendering the anonymized content, such as label policies and indices. Defaults to None.

    Returns:
        Path: The file path to the anonymized DOCX document.
    """
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
    if render_context is not None:
        doc_anonymizer.render_context = render_context

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


def anonymize_document(
    annotations: DocumentAnnotations,
    render_context: dict | None = None,
) -> Path:
    """
    Anonymizes a text document based on provided annotations and returns the path to the anonymized file.

    Args:
        annotations (DocumentAnnotations): The document annotations containing the information needed for anonymization.
        render_context (dict | None, optional): Context for rendering the anonymized content, such as label policies and indices. Defaults to None.

    Returns:
        Path: The file path to the anonymized document.
    """
    # Export as raw document
    anonymized_doc = [
        replace_labels_in_text(
            document_information.model_dump(),
            render_context=render_context,
        )
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
