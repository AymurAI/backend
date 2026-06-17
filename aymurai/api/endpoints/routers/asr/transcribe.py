from fastapi import Body, Depends, UploadFile
from fastapi.routing import APIRouter
from pydantic import UUID5
from sqlmodel import Session

from aymurai.api.exceptions.base import (
    AymuraiAPIException,
    ConfigurationError,
    NotFoundError,
    UpstreamServiceError,
)
from aymurai.audio.asr_client import transcribe_audio_bytes
from aymurai.database.crud.audio_transcription import (
    audio_transcription_create_or_update,
    audio_transcription_get,
)
from aymurai.database.session import get_session
from aymurai.database.utils import data_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import (
    ASRDocument,
    ASRParagraph,
    ASRParagraphRequest,
)
from aymurai.settings import settings

router = APIRouter()
logger = get_logger(__name__)


def get_transcribe_base_url() -> str:
    """
    Get the coro base URL for the transcription service from settings.

    Raises:
        ConfigurationError: If the base URL is not configured in settings.

    Returns:
        str: The coro base URL (e.g. http://localhost:8000/v1).
    """
    base_url = settings.TRANSCRIBE_BASE_URL
    if not base_url:
        raise ConfigurationError(detail="TRANSCRIBE_BASE_URL is not configured")
    return base_url


async def _transcribe_audio_bytes_with_error_handling(
    data: bytes,
    filename: str,
    content_type: str,
) -> list[ASRParagraph]:
    """
    Transcribe audio bytes into a list of ASRParagraph objects via coro.

    Args:
        data (bytes): The audio data to be transcribed.
        filename (str): The uploaded file name.
        content_type (str): The uploaded file MIME type.

    Raises:
        UpstreamServiceError: If the coro service errors or returns no result.
        AymuraiAPIException: If there is an unexpected error during transcription.

    Returns:
        list[ASRParagraph]: The transcribed paragraphs.
    """
    try:
        segments = await transcribe_audio_bytes(data, filename, content_type)
    except RuntimeError as exc:
        raise UpstreamServiceError(detail=str(exc)) from exc
    except Exception as exc:
        raise AymuraiAPIException(
            detail="Unexpected error during transcription"
        ) from exc

    return [
        ASRParagraph(
            speaker_no=int(segment.speaker),
            start=segment.start,
            end=segment.end,
            text=segment.text,
        )
        for segment in segments
    ]


@router.post("/transcribe", response_model=ASRDocument)
async def transcribe(
    file: UploadFile,
    use_cache: bool = True,
    base_url: str = Depends(get_transcribe_base_url),
    session: Session = Depends(get_session),
) -> ASRDocument:
    """
    Transcribes an uploaded audio file and returns the transcribed document.

    Args:
        file (UploadFile): The audio file to be transcribed.
        use_cache (bool, optional): Whether to use cached transcription results. Defaults to True.
        base_url (str, optional): The coro base URL for the transcription service. Defaults to Depends(get_transcribe_base_url).
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Returns:
        ASRDocument: The transcribed audio document.
    """
    data = await file.read()
    document_id = data_to_uuid(data)

    if use_cache:
        cached_record = audio_transcription_get(
            transcription_id=document_id, session=session
        )
        if cached_record is not None:
            logger.debug(f"Audio transcription DB hit for {file.filename}")
            cached_document = ASRDocument(
                document_id=document_id,
                document=cached_record.validation or cached_record.transcription,
            )
            return cached_document

    transcription_items = await _transcribe_audio_bytes_with_error_handling(
        data,
        file.filename or str(document_id),
        file.content_type or "application/octet-stream",
    )
    document = ASRDocument(document_id=document_id, document=transcription_items)
    audio_transcription_create_or_update(
        transcription_id=document_id,
        name=file.filename or str(document_id),
        transcription=document.document,
        session=session,
    )
    logger.debug(f"Audio transcription stored in DB for {file.filename}")

    return document


@router.get("/validation/document/{document_id}")
async def asr_read_document_validation(
    document_id: UUID5,
    session: Session = Depends(get_session),
) -> ASRDocument | None:
    """
    Retrieves the validation document for a given document ID.

    Args:
        document_id (UUID5): The ID of the document to retrieve.
        session (Session, optional): The database session. Defaults to Depends(get_session).


    Raises:
        NotFoundError: If the document with the given ID is not found.

    Returns:
        ASRDocument | None: The validation document if found, otherwise None.
    """
    record = audio_transcription_get(transcription_id=document_id, session=session)
    if not record:
        raise NotFoundError(detail=f"Document not found: {document_id}")

    return ASRDocument(
        document_id=document_id,
        document=record.validation or record.transcription,
    )


@router.post("/validation/document/{document_id}")
async def asr_save_document_validation(
    document_id: UUID5,
    annotations: list[ASRParagraphRequest] = Body(...),
    session: Session = Depends(get_session),
) -> None:
    """
    Saves the validation annotations for a given document ID.

    Args:
        document_id (UUID5): The ID of the document to validate.
        annotations (list[ASRParagraphRequest]): The list of annotations for the document.
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Raises:
        NotFoundError: If the document with the given ID is not found.
    """
    record = audio_transcription_get(transcription_id=document_id, session=session)
    if not record:
        raise NotFoundError(detail=f"Document not found: {document_id}")

    # NOTE: we are serializing the paragraphs to JSON for writing to the DB
    record.validation = [  # type: ignore
        ASRParagraph.model_validate(item).model_dump(mode="json")
        for item in annotations
    ]

    session.add(record)
    session.commit()
    session.refresh(record)
