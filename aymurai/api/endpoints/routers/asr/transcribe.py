from fastapi import Depends, UploadFile
from fastapi.routing import APIRouter
from sqlmodel import Session

from aymurai.api.exceptions.base import (
    AymuraiAPIException,
    ConfigurationError,
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
from aymurai.meta.api_interfaces import ASRDocument, ASRParagraph
from aymurai.settings import settings

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
