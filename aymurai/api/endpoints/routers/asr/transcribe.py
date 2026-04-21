import json
from uuid import UUID

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
from aymurai.audio.asr_client import lines_to_paragraphs, transcribe_audio_bytes
from aymurai.database.crud.audio_transcription import (
    audio_transcription_create_or_update,
    audio_transcription_get,
)
from aymurai.database.session import get_session
from aymurai.database.utils import data_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import ASRDocument, ASRParagraph, ASRParagraphRequest
from aymurai.settings import settings


def _format_transcription_event(
    document_id: UUID,
    paragraphs: list[ASRParagraph],
) -> str:
    """Format an active_transcription SSE event."""
    payload = ASRDocument(
        document_id=document_id, document=paragraphs
    ).model_dump_json()
    return f"event: transcription\ndata: {payload}\n\n"


def _format_done_event(
    document_id: UUID,
    paragraphs: list[ASRParagraph],
) -> str:
    """Format the final 'done' SSE event."""
    payload = ASRDocument(
        document_id=document_id, document=paragraphs
    ).model_dump_json()
    return f"event: done\ndata: {payload}\n\n"


def _format_error_event(detail: str, code: str) -> str:
    """Format an error SSE event."""
    payload = json.dumps({"detail": detail, "code": code})
    return f"event: error\ndata: {payload}\n\n"


router = APIRouter()
logger = get_logger(__name__)


def get_transcribe_ws_uri() -> str:
    """
    Get the WebSocket URI for the transcription service from settings.

    Raises:
        ConfigurationError: If the WebSocket URI is not configured in settings.

    Returns:
        str: The WebSocket URI for the transcription service.
    """
    ws_uri = settings.TRANSCRIBE_WS_URI
    if not ws_uri:
        raise ConfigurationError(detail="TRANSCRIBE_WS_URI is not configured")
    return ws_uri


async def _transcribe_audio_bytes_with_error_handling(
    data: bytes,
) -> list[ASRParagraph]:
    """
    Transcribes audio bytes into a list of ASRParagraph objects.

    Args:
        data (bytes): The audio data to be transcribed.

    Raises:
        UpstreamServiceError: If there is an error with the upstream transcription service.
        AymuraiAPIException: If there is an unexpected error during transcription.

    Returns:
        list[ASRParagraph]: A list of ASRParagraph objects representing the transcribed audio.
    """
    try:
        status = await transcribe_audio_bytes(data)
    except RuntimeError as exc:
        message = str(exc)
        if "websocket" in message.lower():
            raise UpstreamServiceError(detail=message) from exc
        raise AymuraiAPIException(detail=message) from exc
    except Exception as exc:
        raise AymuraiAPIException(
            detail="Unexpected error during transcription"
        ) from exc

    if not status:
        raise AymuraiAPIException(detail="No transcription result received")

    return lines_to_paragraphs(status.lines)


@router.post("/transcribe", response_model=ASRDocument)
async def transcribe(
    file: UploadFile,
    use_cache: bool = True,
    ws_uri: str = Depends(get_transcribe_ws_uri),
    session: Session = Depends(get_session),
) -> ASRDocument:
    """
    Transcribes an uploaded audio file and returns the transcribed document.

    Args:
        file (UploadFile): The audio file to be transcribed.
        use_cache (bool, optional): Whether to use cached transcription results. Defaults to True.
        ws_uri (str, optional): The WebSocket URI for the transcription service. Defaults to Depends(get_transcribe_ws_uri).
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

    transcription_items = await _transcribe_audio_bytes_with_error_handling(data)
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
        annotations (list[ASRParagraphRequest], optional): The list of annotations for the document. Defaults to Body(...).
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
