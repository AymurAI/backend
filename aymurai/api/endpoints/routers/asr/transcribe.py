import asyncio
import contextlib
import json
from typing import AsyncGenerator
from uuid import UUID

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
from aymurai.audio.asr_client import (
    ASRStreamChunk,
    lines_to_paragraphs,
    transcribe_audio_bytes,
    transcribe_audio_bytes_stream,
)
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
    current_time: float | None = None,
    total_time: float | None = None,
) -> str:
    """Format an active_transcription SSE event."""
    payload = ASRDocument(
        document_id=document_id,
        document=paragraphs,
        current_time=current_time,
        total_time=total_time,
    ).model_dump_json()
    return f"event: transcription\ndata: {payload}\n\n"


def _format_done_event(
    document_id: UUID,
    paragraphs: list[ASRParagraph],
    current_time: float | None = None,
    total_time: float | None = None,
) -> str:
    """Format the final 'done' SSE event."""
    payload = ASRDocument(
        document_id=document_id,
        document=paragraphs,
        current_time=current_time,
        total_time=total_time,
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


@router.post(
    "/transcribe",
    response_model=ASRDocument,
    deprecated=True,
)
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
            logger.debug("Audio transcription DB hit for %s", file.filename)
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
    logger.debug("Audio transcription stored in DB for %s", file.filename)

    return document


@router.post("/transcribe/stream")
async def transcribe_stream(
    file: UploadFile,
    use_cache: bool = True,
    ws_uri: str = Depends(get_transcribe_ws_uri),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """
    Transcribe an uploaded audio file and stream intermediate results as SSE.

    Emits `event: transcription` frames per upstream update (cumulative snapshots),
    a final `event: done` frame with the complete ASRDocument, and `event: error`
    on upstream failure. Checks the cache first; on cache miss, persists the final
    result.
    """
    data = await file.read()
    filename = file.filename
    document_id = data_to_uuid(data)

    async def _event_stream() -> AsyncGenerator[str, None]:
        # Cache check
        if use_cache:
            cached = audio_transcription_get(
                transcription_id=document_id, session=session
            )
            if cached is not None:
                logger.debug("Audio transcription DB hit for %s", filename)
                cached_paragraphs = [
                    ASRParagraph.model_validate(p)
                    for p in (cached.validation or cached.transcription)
                ]
                yield _format_done_event(document_id, cached_paragraphs)
                return

        # Live streaming path
        keepalive_task: asyncio.Task | None = None
        keepalive_queue: asyncio.Queue[str] = asyncio.Queue()
        interval = settings.TRANSCRIBE_SSE_KEEPALIVE_SECONDS

        async def _keepalive_pump() -> None:
            while True:
                await asyncio.sleep(interval)
                await keepalive_queue.put(": keepalive\n\n")

        if interval > 0:
            keepalive_task = asyncio.create_task(_keepalive_pump())

        last_snapshot: list[ASRParagraph] = []
        last_current_time: float | None = None
        last_total_time: float | None = None
        stream_iter = transcribe_audio_bytes_stream(data).__aiter__()

        try:
            # next_task is created once and reused across keepalive interruptions so
            # that cancelling the keepalive_get task never aborts the in-flight
            # __anext__() call.
            next_task: asyncio.Task[ASRStreamChunk] = asyncio.create_task(
                stream_iter.__anext__()
            )
            while True:
                keepalive_get = asyncio.create_task(keepalive_queue.get())

                done, _ = await asyncio.wait(
                    {next_task, keepalive_get},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if keepalive_get in done:
                    yield keepalive_get.result()
                else:
                    # keepalive_get lost the race — discard it cleanly
                    keepalive_get.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await keepalive_get

                if next_task in done:
                    try:
                        chunk: ASRStreamChunk = next_task.result()
                    except StopAsyncIteration:
                        break
                    except RuntimeError as exc:
                        logger.error("upstream error during streaming: %s", exc)
                        yield _format_error_event(
                            detail=str(exc), code="UPSTREAM_SERVICE_ERROR"
                        )
                        return
                    except Exception:
                        logger.exception("unexpected error during streaming")
                        yield _format_error_event(
                            detail="Unexpected error during transcription",
                            code="INTERNAL_ERROR",
                        )
                        return
                    last_snapshot = chunk.paragraphs
                    last_current_time = chunk.current_time
                    last_total_time = chunk.total_time
                    yield _format_transcription_event(
                        document_id,
                        chunk.paragraphs,
                        current_time=chunk.current_time,
                        total_time=chunk.total_time,
                    )
                    # Advance to the next chunk only after the current one is consumed
                    next_task = asyncio.create_task(stream_iter.__anext__())
        finally:
            if keepalive_task is not None and not keepalive_task.done():
                keepalive_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await keepalive_task
            with contextlib.suppress(Exception):
                await stream_iter.aclose()  # type: ignore[attr-defined]

        # Persist + done event
        try:
            audio_transcription_create_or_update(
                transcription_id=document_id,
                name=filename or str(document_id),
                transcription=last_snapshot,
                session=session,
            )
            logger.debug("Audio transcription stored in DB for %s", filename)
        except Exception:
            logger.exception("failed to persist transcription; continuing")

        yield _format_done_event(
            document_id,
            last_snapshot,
            current_time=last_current_time,
            total_time=last_total_time,
        )

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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
