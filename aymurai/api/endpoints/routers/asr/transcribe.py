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
from aymurai.meta.api_interfaces import ASRDocument, ASRParagraph, ASRParagraphRequest
from aymurai.settings import settings
from aymurai.utils.cache import cache_save

router = APIRouter()
logger = get_logger(__name__)


def get_transcribe_ws_uri() -> str:
    ws_uri = settings.TRANSCRIBE_WS_URI
    if not ws_uri:
        raise ConfigurationError(detail="TRANSCRIBE_WS_URI is not configured")
    return ws_uri


async def _transcribe_audio_bytes_with_error_handling(
    data: bytes,
) -> list[ASRParagraph]:
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

    return [
        ASRParagraph(
            speaker_no=line.speaker,
            speaker_id=f"speaker-{line.speaker}",
            start=line.start,
            end=line.end,
            text=line.text,
        )
        for line in status.lines
    ]


@router.post("/transcribe", response_model=ASRDocument)
async def transcribe(
    file: UploadFile,
    use_cache: bool = True,
    ws_uri: str = Depends(get_transcribe_ws_uri),
    session: Session = Depends(get_session),
) -> ASRDocument:
    """
    Stream an uploaded audio file to an external websocket transcription service.
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
            cache_save(cached_document, key=str(document_id))
            return cached_document

    transcription_items = await _transcribe_audio_bytes_with_error_handling(data)
    document = ASRDocument(document_id=document_id, document=transcription_items)
    audio_transcription_create_or_update(
        transcription_id=document_id,
        name=file.filename or str(document_id),
        transcription=document.document,
        session=session,
    )
    cache_save(document, key=str(document_id))
    logger.debug(f"Audio transcription stored in DB for {file.filename}")

    return document


@router.get("/validation/document/{document_id}")
async def asr_read_document_validation(
    document_id: UUID5,
    session: Session = Depends(get_session),
) -> ASRDocument | None:
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
