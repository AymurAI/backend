from __future__ import annotations

import asyncio
import contextlib
import io
import json
from typing import AsyncGenerator

import librosa
import numpy as np
import websockets
from pydantic import BaseModel, TypeAdapter, ValidationError

from aymurai.api.meta.asr.websocket import (
    WLKMessageRawResponse,
    WLKMessageReadyToStopMessage,
    WLKMessageStatus,
    WLKMessageTranscriptionLine,
)
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import ASRParagraph
from aymurai.settings import settings

logger = get_logger(__name__)

MAX_WS_LOG_CHARS = 2000
ASR_RAW_RESPONSE_ADAPTER = TypeAdapter(WLKMessageRawResponse)


def _describe_ws_exception(exc: BaseException) -> str:
    """Render a WebSocket exception with structured detail.

    For ``ConnectionClosed`` (and subclasses), surfaces the close
    ``code`` and ``reason`` from both the received and sent frames.
    This distinguishes e.g. an upstream 1011 crash from a client-side
    keepalive timeout vs. a normal close (1000/1001).
    """
    # Lazy import-safe access: ConnectionClosed is defined in websockets.exceptions
    closed = getattr(websockets.exceptions, "ConnectionClosed", None)
    if closed is not None and isinstance(exc, closed):
        rcvd = getattr(exc, "rcvd", None)
        sent = getattr(exc, "sent", None)
        rcvd_desc = (
            f"code={rcvd.code} reason={rcvd.reason!r}" if rcvd is not None else "None"
        )
        sent_desc = (
            f"code={sent.code} reason={sent.reason!r}" if sent is not None else "None"
        )
        return f"{type(exc).__name__}: {exc} | rcvd=({rcvd_desc}) sent=({sent_desc})"
    return f"{type(exc).__name__}: {exc}"


class ASRStreamChunk(BaseModel):
    """A single snapshot yielded by ``transcribe_audio_bytes_stream``.

    Attributes:
        paragraphs: Cumulative list of transcribed paragraphs so far.
        current_time: Seconds of audio covered by the transcription so far
            (``end`` timestamp of the last line), or ``None`` if no lines.
        total_time: Estimated total audio duration in seconds, or ``None``.
    """

    paragraphs: list[ASRParagraph]
    current_time: float | None = None
    total_time: float | None = None


class _DecodedAudio:
    """Result of decoding an audio payload — array and duration."""

    __slots__ = ("array", "duration_s")

    def __init__(self, array: np.ndarray, duration_s: float) -> None:
        self.array = array
        self.duration_s = duration_s


def _decode_audio(payload: bytes, sr: int = 16000) -> _DecodedAudio:
    """Decode an audio payload to a mono float32 array at Sample Rate ``sr``.

    Pure CPU/IO work — call via ``asyncio.to_thread`` from async contexts
    to avoid blocking the event loop (which would starve WebSocket and SSE
    keepalives).
    """
    audio, _ = librosa.load(io.BytesIO(payload), sr=sr, mono=True)
    return _DecodedAudio(array=audio, duration_s=len(audio) / sr)


def _current_time_from_status(message: WLKMessageStatus) -> float | None:
    """Return the end timestamp of the last transcription line in seconds, or None."""
    if not message.lines:
        return None
    return message.lines[-1].end.total_seconds()


def lines_to_paragraphs(
    lines: list[WLKMessageTranscriptionLine],
) -> list[ASRParagraph]:
    """Map WebSocket transcription lines to ASRParagraph objects.

    Args:
        lines: Transcription lines from the ASR service.

    Returns:
        ASRParagraph objects ready for serialization or storage.
    """
    return [
        ASRParagraph(
            speaker_no=line.speaker,
            start=line.start,
            end=line.end,
            text=line.text,
        )
        for line in lines
    ]


async def _stream_audio_bytes(
    payload: bytes | _DecodedAudio,
    websocket: websockets.ClientConnection,
) -> int:
    """Stream audio bytes to a WebSocket connection in chunks.

    Sleeps briefly between chunks (``TRANSCRIBE_WS_CHUNK_SLEEP_SECONDS``)
    to yield control to the event loop so the recv task can drain incoming
    frames and keepalive pings stay responsive.

    Args:
        payload: The audio data (raw bytes or pre-decoded ``_DecodedAudio``).
        websocket: The WebSocket connection to stream the audio data to.

    Returns:
        The total number of bytes sent to the WebSocket.
    """
    if isinstance(payload, _DecodedAudio):
        decoded = payload
    else:
        decoded = await asyncio.to_thread(
            _decode_audio,
            payload,
            sr=settings.TRANSCRIBE_WS_SAMPLE_RATE,
        )
    audio = decoded.array

    total_bytes = 0
    _CHUNK_SAMPLES = settings.TRANSCRIBE_WS_CHUNK_SAMPLES
    for i in range(0, len(audio), _CHUNK_SAMPLES):
        chunk = audio[i : i + _CHUNK_SAMPLES]
        if len(chunk) == 0:
            continue
        chunk_int16 = (chunk * 32768).astype(np.int16)
        data = chunk_int16.tobytes()
        total_bytes += len(data)

        await websocket.send(data)

        # add a small sleep after each chunk to yield control to the event loop and
        # allow the receive task to process incoming messages
        await asyncio.sleep(settings.TRANSCRIBE_WS_CHUNK_SLEEP_SECONDS)

    return total_bytes


def _parse_ws_message(message: str | bytes) -> WLKMessageRawResponse | None:
    """Parse a WebSocket message into a WLKMessageRawResponse object.

    Args:
        message: The WebSocket message to be parsed.

    Returns:
        The parsed WLKMessageRawResponse object, or None if parsing fails.
    """
    if isinstance(message, bytes):
        message = message.decode("utf-8", errors="replace")

    payload_preview = message
    if len(payload_preview) > MAX_WS_LOG_CHARS:
        payload_preview = (
            f"{payload_preview[:MAX_WS_LOG_CHARS]}"
            f"...[truncated {len(payload_preview) - MAX_WS_LOG_CHARS} chars]"
        )

    try:
        parsed = json.loads(message)
    except json.JSONDecodeError:
        logger.warning("received non-json websocket payload: %s", payload_preview)
        return None

    try:
        return ASR_RAW_RESPONSE_ADAPTER.validate_python(parsed)
    except ValidationError as exc:
        logger.warning(
            "received unrecognized websocket payload: %s; payload=%s",
            exc,
            payload_preview,
        )
        return None


async def _iter_ws_messages(
    websocket: websockets.ClientConnection,
) -> AsyncGenerator[WLKMessageStatus, None]:
    """Yield ``active_transcription`` status messages from a WebSocket.

    Handles recv errors and message parsing internally. Yields only
    ``WLKMessageStatus`` messages with ``status="active_transcription"``;
    silently skips unparseable messages and ``WLKMessageConfig`` messages.
    Terminates on ``ConnectionClosedOK`` or ``WLKMessageReadyToStopMessage``.

    Args:
        websocket: The WebSocket connection to receive from.

    Yields:
        Each active_transcription status received from the server.

    Raises:
        RuntimeError: On WebSocket errors during receive.
    """
    while True:
        try:
            msg = await websocket.recv()
        except websockets.exceptions.ConnectionClosedOK:
            logger.info("connection closed normally")
            return
        except websockets.exceptions.WebSocketException as exc:
            logger.error(
                "websocket error while receiving: %s",
                _describe_ws_exception(exc),
            )
            raise RuntimeError("Transcription service websocket error") from exc

        parsed = _parse_ws_message(msg)
        match parsed:
            case None:
                continue
            case WLKMessageStatus(status="active_transcription") as message:
                yield message
            case WLKMessageReadyToStopMessage():
                return


async def _receive_updates(
    websocket: websockets.ClientConnection,
) -> WLKMessageStatus | None:
    """Receive updates from the WebSocket connection.

    Args:
        websocket: The WebSocket connection to receive updates from.

    Returns:
        The last active transcription status, or None if none received.
    """
    last_active_transcription: WLKMessageStatus | None = None
    async for message in _iter_ws_messages(websocket):
        last_active_transcription = message
    return last_active_transcription


async def transcribe_audio_bytes(payload: bytes) -> WLKMessageStatus | None:
    """Transcribe audio bytes via the WebSocket ASR service.

    Args:
        payload: The audio data to be transcribed.

    Raises:
        RuntimeError: If there is an error with the transcription service.

    Returns:
        The last active transcription status, or None if none received.
    """
    ws_uri = settings.TRANSCRIBE_WS_URI

    if not ws_uri:
        raise RuntimeError("TRANSCRIBE_WS_URI is not configured")

    logger.info("streaming audio for transcription")

    ping_interval = settings.TRANSCRIBE_WS_PING_INTERVAL_SECONDS or None
    ping_timeout = settings.TRANSCRIBE_WS_PING_TIMEOUT_SECONDS or None
    try:
        async with websockets.connect(
            ws_uri, ping_interval=ping_interval, ping_timeout=ping_timeout
        ) as websocket:
            receive_task = asyncio.create_task(_receive_updates(websocket))
            try:
                total_bytes = await _stream_audio_bytes(payload, websocket)
                await websocket.send(b"")
                logger.info("sent %s bytes to transcription service", total_bytes)
                last_active_transcription = await receive_task
            except Exception:
                if not receive_task.done():
                    receive_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await receive_task
                raise
    except RuntimeError:
        raise
    except websockets.exceptions.WebSocketException as exc:
        logger.error(
            "websocket error during transcription: %s", _describe_ws_exception(exc)
        )
        raise RuntimeError("Transcription service websocket error") from exc
    except Exception as exc:
        logger.error("unexpected error during transcription: %s", exc)
        raise RuntimeError("Unexpected error during transcription") from exc

    return last_active_transcription


async def transcribe_audio_bytes_stream(
    payload: bytes,
) -> AsyncGenerator[ASRStreamChunk, None]:
    """Stream transcription updates from the ASR WebSocket service.

    Yields an ``ASRStreamChunk`` for each intermediate active_transcription
    update received from the upstream service. Each chunk contains a cumulative
    paragraph snapshot and progress information (current_time / total_time in
    seconds). The generator terminates when the service sends a ready_to_stop
    message or the connection closes normally.

    Args:
        payload: The audio data to be transcribed.

    Raises:
        RuntimeError: If TRANSCRIBE_WS_URI is not configured or the upstream
            websocket service errors out mid-stream.

    Yields:
        ASRStreamChunk: Cumulative snapshot of paragraphs together with
            ``current_time`` and ``total_time`` progress values.
    """
    ws_uri = settings.TRANSCRIBE_WS_URI

    if not ws_uri:
        raise RuntimeError("TRANSCRIBE_WS_URI is not configured")

    logger.info("streaming audio for transcription (sse)")

    ping_interval = settings.TRANSCRIBE_WS_PING_INTERVAL_SECONDS or None
    ping_timeout = settings.TRANSCRIBE_WS_PING_TIMEOUT_SECONDS or None

    streaming_task: asyncio.Task | None = None
    decoded = await asyncio.to_thread(_decode_audio, payload)
    total_time = decoded.duration_s
    try:
        async with websockets.connect(
            ws_uri, ping_interval=ping_interval, ping_timeout=ping_timeout
        ) as websocket:
            streaming_task = asyncio.create_task(
                _stream_and_signal_end(decoded, websocket)
            )
            async for message in _iter_ws_messages(websocket):
                current_time = _current_time_from_status(message)
                yield ASRStreamChunk(
                    paragraphs=lines_to_paragraphs(message.lines),
                    current_time=current_time,
                    total_time=total_time,
                )
    except websockets.exceptions.WebSocketException as exc:
        logger.error(
            "websocket error during transcription: %s", _describe_ws_exception(exc)
        )
        raise RuntimeError("Transcription service websocket error") from exc
    finally:
        if streaming_task is not None:
            if not streaming_task.done():
                streaming_task.cancel()
            try:
                await streaming_task
            except asyncio.CancelledError:
                pass  # expected when we cancelled it
            except Exception as exc:
                logger.error("audio streaming task failed: %s", exc)


async def _stream_and_signal_end(
    payload: bytes | _DecodedAudio,
    websocket: websockets.ClientConnection,
) -> None:
    """Stream audio bytes then send the empty end-of-stream marker."""
    total_bytes = await _stream_audio_bytes(payload, websocket)
    await websocket.send(b"")
    logger.info("sent %s bytes to transcription service", total_bytes)
