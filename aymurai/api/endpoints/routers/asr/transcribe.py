import json
import math
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Body, Depends, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRouter
from pydantic import UUID5
from sqlmodel import Session

from aymurai.api.exceptions.base import (
    AymuraiAPIException,
    ConfigurationError,
    NotFoundError,
    UpstreamServiceError,
)
from aymurai.api.meta.asr.coro import (
    CoroSegment,
    CoroStreamDelta,
    CoroStreamSegments,
)
from aymurai.audio.asr_client import (
    stream_transcribe_audio_bytes,
    transcribe_audio_bytes,
)
from aymurai.audio.duration import probe_audio_duration
from aymurai.audio.transcript import transcript_turns
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
    ASRSpeakerTurn,
)
from aymurai.settings import settings

router = APIRouter()
logger = get_logger(__name__)

# Progress estimation tuning (see docs/superpowers/specs/2026-06-19-asr-streaming-progress-design.md).
# CHARS_PER_SEC biases the estimate: higher values make the bar lag and snap to
# 100% on completion rather than peg early. K = ln(10) puts the displayed value
# at ~90% when the char estimate thinks transcription is done (raw == 1.0).
ASR_PROGRESS_CHARS_PER_SEC = 17.0
ASR_PROGRESS_K = math.log(10)


def _estimate_progress(cumulative_chars: int, duration_s: float | None) -> float | None:
    """
    Estimate transcription progress with an asymptotic easing curve.

    Computes ``1 - exp(-k * raw)`` where ``raw`` is the ratio of characters seen
    so far to the expected total (``duration_s * ASR_PROGRESS_CHARS_PER_SEC``).
    The curve never reaches 1.0, so it decelerates near the top instead of
    pinning to a hard cap; completion is signalled separately by the done event.

    Args:
        cumulative_chars (int): Characters received from deltas so far.
        duration_s (float | None): Audio duration in seconds, or None if unknown.

    Returns:
        float | None: Progress in [0.0, 1.0), or None if duration is unknown.
    """
    if not duration_s or duration_s <= 0:
        return None
    raw = cumulative_chars / (duration_s * ASR_PROGRESS_CHARS_PER_SEC)
    value = 1.0 - math.exp(-ASR_PROGRESS_K * raw)
    # Guard the float-underflow corner so deltas stay strictly below 1.0
    # (1.0 is reserved for the done event). This only corrects the artifact at
    # extreme raw values; it is not a visible cap.
    return min(value, math.nextafter(1.0, 0.0))


def _segments_to_paragraphs(segments: list[CoroSegment]) -> list[ASRParagraph]:
    """
    Map coro segments to ASRParagraph objects.

    Args:
        segments (list[CoroSegment]): The coro speaker-attributed segments.

    Returns:
        list[ASRParagraph]: The transcribed paragraphs.
    """
    return [
        ASRParagraph(
            speaker_no=int(segment.speaker),
            start=segment.start,
            end=segment.end,
            text=segment.text,
        )
        for segment in segments
    ]


def _speaker_turns_for_paragraphs(
    paragraphs: list[ASRParagraph],
) -> list[ASRSpeakerTurn]:
    if not paragraphs:
        return []
    return [
        ASRSpeakerTurn.model_validate(turn)
        for turn in transcript_turns({"document": paragraphs})
    ]


def _asr_document(document_id: UUID5, paragraphs: list[ASRParagraph]) -> ASRDocument:
    return ASRDocument(
        document_id=document_id,
        document=paragraphs,
        speaker_turns=_speaker_turns_for_paragraphs(paragraphs),
    )


def _build_sse_message(payload: dict[str, Any]) -> str:
    """
    Format a payload as an SSE data message.

    Args:
        payload (dict[str, Any]): Dictionary to serialize into the SSE data field.

    Returns:
        str: Serialized SSE message string.
    """
    return f"data: {json.dumps(payload)}\n\n"


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

    return _segments_to_paragraphs(segments)


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
            logger.debug("Audio transcription DB hit for %s", file.filename)
            cached_paragraphs = [
                ASRParagraph.model_validate(item)
                for item in (cached_record.validation or cached_record.transcription)
            ]
            return _asr_document(document_id, cached_paragraphs)

    transcription_items = await _transcribe_audio_bytes_with_error_handling(
        data,
        file.filename or str(document_id),
        file.content_type or "application/octet-stream",
    )
    document = _asr_document(document_id, transcription_items)
    audio_transcription_create_or_update(
        transcription_id=document_id,
        name=file.filename or str(document_id),
        transcription=document.document,
        session=session,
    )
    logger.debug("Audio transcription stored in DB for %s", file.filename)

    return document


@router.post("/transcribe/stream")
async def transcribe_stream(
    file: UploadFile,
    use_cache: bool = True,
    base_url: str = Depends(get_transcribe_base_url),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """
    Transcribe an uploaded audio file and stream progress via Server-Sent Events.

    Emits ``data: {json}`` SSE messages with a ``type`` discriminator:
        - meta: ``{document_id, duration}`` (duration is null if unknown)
        - delta: ``{text, progress?}`` incremental text (progress omitted if no duration)
        - segments: ``{document}`` the final paragraph list
        - done: ``{progress: 1.0}`` terminal success
        - error: ``{detail}`` upstream/internal failure

    On a cache hit it emits meta, segments, done without calling coro.

    Args:
        file (UploadFile): The audio file to be transcribed.
        use_cache (bool, optional): Whether to use cached results. Defaults to True.
        base_url (str, optional): The coro base URL. Defaults to Depends(get_transcribe_base_url).
        session (Session, optional): The database session. Defaults to Depends(get_session).

    Returns:
        StreamingResponse: A text/event-stream of transcription progress events.
    """
    data = await file.read()
    document_id = data_to_uuid(data)
    filename = file.filename or str(document_id)
    content_type = file.content_type or "application/octet-stream"

    cached_paragraphs: list[ASRParagraph] | None = None
    if use_cache:
        cached_record = audio_transcription_get(
            transcription_id=document_id, session=session
        )
        if cached_record is not None:
            cached_paragraphs = [
                ASRParagraph.model_validate(item)
                for item in (cached_record.validation or cached_record.transcription)
            ]

    duration = probe_audio_duration(data)

    async def event_stream() -> AsyncIterator[str]:
        yield _build_sse_message(
            {
                "type": "meta",
                "document_id": str(document_id),
                "duration": duration,
            }
        )

        if cached_paragraphs is not None:
            yield _build_sse_message(
                {
                    "type": "segments",
                    "document": [
                        paragraph.model_dump(mode="json")
                        for paragraph in cached_paragraphs
                    ],
                    "speaker_turns": [
                        turn.model_dump(mode="json")
                        for turn in _speaker_turns_for_paragraphs(cached_paragraphs)
                    ],
                }
            )
            yield _build_sse_message({"type": "done", "progress": 1.0})
            return

        cumulative_chars = 0
        try:
            async for event in stream_transcribe_audio_bytes(
                data, filename, content_type
            ):
                if isinstance(event, CoroStreamDelta):
                    cumulative_chars += len(event.text)
                    payload: dict[str, Any] = {"type": "delta", "text": event.text}
                    progress = _estimate_progress(cumulative_chars, duration)
                    if progress is not None:
                        payload["progress"] = progress
                    yield _build_sse_message(payload)
                elif isinstance(event, CoroStreamSegments):
                    paragraphs = _segments_to_paragraphs(event.segments)
                    audio_transcription_create_or_update(
                        transcription_id=document_id,
                        name=filename,
                        transcription=paragraphs,
                        session=session,
                    )
                    yield _build_sse_message(
                        {
                            "type": "segments",
                            "document": [
                                paragraph.model_dump(mode="json")
                                for paragraph in paragraphs
                            ],
                            "speaker_turns": [
                                turn.model_dump(mode="json")
                                for turn in _speaker_turns_for_paragraphs(paragraphs)
                            ],
                        }
                    )
        except RuntimeError as exc:
            logger.error("asr stream error: %s", exc)
            yield _build_sse_message({"type": "error", "detail": str(exc)})
            return

        yield _build_sse_message({"type": "done", "progress": 1.0})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
