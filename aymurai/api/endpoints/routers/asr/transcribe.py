from hashlib import blake2b
from io import BytesIO

from fastapi import Depends, UploadFile
from fastapi.routing import APIRouter

from aymurai.api.exceptions.base import (
    AymuraiAPIException,
    ConfigurationError,
    UpstreamServiceError,
)
from aymurai.audio.asr_client import transcribe_audio_bytes
from aymurai.database.utils import data_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import ASRDocument, ASRParagraph
from aymurai.settings import settings
from aymurai.utils.cache import cache_load, cache_save, get_cache_key

router = APIRouter()
logger = get_logger(__name__)


def get_transcribe_ws_uri() -> str:
    ws_uri = settings.TRANSCRIBE_WS_URI
    if not ws_uri:
        raise ConfigurationError(detail="TRANSCRIBE_WS_URI is not configured")
    return ws_uri


def _cache_key(data: bytes) -> str:
    try:
        hasher = blake2b(digest_size=32)
        with BytesIO(data) as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                hasher.update(chunk)
        fingerprint = hasher.hexdigest()
        stat = handle.getbuffer()

        return get_cache_key(
            fingerprint,
            context={"component": "audio-extractor", "size": stat.nbytes},
        )
    except OSError as exc:
        raise RuntimeError("Failed to generate cache key") from exc


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
            speaker_id=line.speaker_id or f"speaker-{line.speaker}",
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
) -> ASRDocument:
    """
    Stream an uploaded audio file to an external websocket transcription service.
    """
    data = await file.read()
    document_id = data_to_uuid(data)

    if use_cache:
        cached_text = cache_load(str(document_id))
        if cached_text is not None:
            logger.debug(f"Audio cache hit for {file.filename}")
            return ASRDocument.model_validate_json(cached_text)

    transcription_items = await _transcribe_audio_bytes_with_error_handling(data)
    document = ASRDocument(document_id=document_id, document=transcription_items)

    cache_save(document.model_dump_json(), key=str(document_id))
    logger.debug(f"Audio cache stored for {file.filename}")

    return document
