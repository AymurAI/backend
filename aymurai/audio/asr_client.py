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

SAMPLE_RATE_HZ = 16000
CHUNK_SECONDS = 1
CHUNK_SAMPLES = SAMPLE_RATE_HZ * CHUNK_SECONDS
MAX_WS_LOG_CHARS = 2000
ASR_RAW_RESPONSE_ADAPTER = TypeAdapter(WLKMessageRawResponse)


class _Backpressure:
    """Lead-budget backpressure for the ASR send loop.

    The upstream WhisperLiveKit server runs on uvicorn with a bounded
    WebSocket frame queue (``ws_max_queue`` defaults to 32 frames). If
    we push audio faster than the server consumes it, the queue fills,
    the frame reader blocks, and PING control frames in the TCP buffer
    never get processed in time — causing 1011 ``keepalive ping timeout``
    closes.

    We cap how far *ahead* of the server's progress we send.  Progress
    is ``max(server_current_time, wallclock_elapsed - initial_grace)``.
    The wall-clock fallback prevents deadlocking during silence stretches.

    Attributes:
        lead_budget_s: Max seconds of audio we're allowed to be ahead
            of the server's effective progress.
        initial_grace_s: Wall-clock headroom before pacing kicks in.
            Also the catch-up factor during silence gaps.
        wait_poll_s: Polling interval while paused.
    """

    def __init__(
        self,
        lead_budget_s: float,
        initial_grace_s: float,
        wait_poll_s: float = 0.25,
    ) -> None:
        self.lead_budget_s = lead_budget_s
        self.initial_grace_s = initial_grace_s
        self.wait_poll_s = wait_poll_s
        self._audio_sent_s: float = 0.0
        self._server_progress_s: float = 0.0
        self._start_monotonic: float | None = None
        self._update_event: asyncio.Event = asyncio.Event()

    def mark_started(self) -> None:
        """Record the wall-clock reference for pacing fallback."""
        self._start_monotonic = asyncio.get_running_loop().time()

    def record_sent(self, audio_seconds: float) -> None:
        """Called by the send loop after streaming ``audio_seconds`` of audio."""
        self._audio_sent_s += audio_seconds

    def update_server_progress(self, current_time_s: float | None) -> None:
        """Called by the recv loop with the server's last-line end timestamp."""
        if current_time_s is None:
            return
        if current_time_s > self._server_progress_s:
            self._server_progress_s = current_time_s
        # Wake the send loop so it can recheck the budget.
        self._update_event.set()

    def _effective_progress(self) -> float:
        start = self._start_monotonic
        if start is None:
            wallclock = 0.0
        else:
            elapsed = asyncio.get_running_loop().time() - start
            wallclock = max(0.0, elapsed - self.initial_grace_s)
        return max(self._server_progress_s, wallclock)

    async def wait_if_needed(self) -> None:
        """Block until our lead over the server's effective progress is OK."""
        lead = self._audio_sent_s - self._effective_progress()
        if lead <= self.lead_budget_s:
            return

        logger.debug(
            "backpressure: pausing send lead=%.1fs > budget=%.1fs "
            "(sent=%.1fs server=%.1fs)",
            lead,
            self.lead_budget_s,
            self._audio_sent_s,
            self._server_progress_s,
        )
        while True:
            self._update_event.clear()
            # Wait either for a server update or a short poll so the
            # wall-clock fallback can re-advance the effective progress.
            try:
                await asyncio.wait_for(
                    self._update_event.wait(), timeout=self.wait_poll_s
                )
            except asyncio.TimeoutError:
                pass
            lead = self._audio_sent_s - self._effective_progress()
            if lead <= self.lead_budget_s:
                logger.debug(
                    "backpressure: resuming send lead=%.1fs <= budget=%.1fs "
                    "(sent=%.1fs server=%.1fs)",
                    lead,
                    self.lead_budget_s,
                    self._audio_sent_s,
                    self._server_progress_s,
                )
                return


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


def _decode_audio(payload: bytes) -> _DecodedAudio:
    """Decode an audio payload to a mono float32 array at SAMPLE_RATE_HZ.

    Pure CPU/IO work — call via ``asyncio.to_thread`` from async contexts
    to avoid blocking the event loop (which would starve WebSocket and SSE
    keepalives).
    """
    audio, _ = librosa.load(io.BytesIO(payload), sr=SAMPLE_RATE_HZ, mono=True)
    return _DecodedAudio(array=audio, duration_s=len(audio) / SAMPLE_RATE_HZ)


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
    backpressure: _Backpressure | None = None,
) -> int:
    """Stream audio bytes to a WebSocket connection in chunks.

    If ``backpressure`` is supplied, pause between chunks whenever the
    upstream ASR service's transcription backlog grows past the configured
    high-water mark. This prevents saturating the server's WebSocket frame
    queue, which would otherwise starve control-frame handling and cause
    1011 "keepalive ping timeout" closes.

    Args:
        payload: The audio data (raw bytes or pre-decoded ``_DecodedAudio``).
        websocket: The WebSocket connection to stream the audio data to.
        backpressure: Optional adaptive pacer fed by the recv loop. When
            ``None``, sends at maximum TCP-permitted rate (legacy behavior).

    Returns:
        The total number of bytes sent to the WebSocket.
    """
    if isinstance(payload, _DecodedAudio):
        decoded = payload
    else:
        decoded = await asyncio.to_thread(_decode_audio, payload)
    audio = decoded.array
    if backpressure is not None:
        backpressure.mark_started()
    total_bytes = 0
    for i in range(0, len(audio), CHUNK_SAMPLES):
        chunk = audio[i : i + CHUNK_SAMPLES]
        if len(chunk) == 0:
            continue
        chunk_int16 = (chunk * 32768).astype(np.int16)
        data = chunk_int16.tobytes()
        total_bytes += len(data)
        chunk_seconds = len(chunk) / SAMPLE_RATE_HZ
        if backpressure is not None:
            await backpressure.wait_if_needed()
        await websocket.send(data)
        if backpressure is not None:
            backpressure.record_sent(chunk_seconds)
    return total_bytes


def _parse_ws_message(message: str | bytes) -> WLKMessageRawResponse | None:
    """
    Parses a WebSocket message into a WLKMessageRawResponse object.

    Args:
        message (str | bytes): The WebSocket message to be parsed.

    Returns:
        WLKMessageRawResponse | None: The parsed WLKMessageRawResponse object, or None if parsing fails.
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


async def _receive_updates(
    websocket: websockets.ClientConnection,
    backpressure: _Backpressure | None = None,
) -> WLKMessageStatus | None:
    """Receive updates from the WebSocket connection.

    Args:
        websocket: The WebSocket connection to receive updates from.
        backpressure: Optional pacer to feed with server progress updates.

    Returns:
        The last active transcription status, or None if none received.
    """
    last_active_transcription: WLKMessageStatus | None = None
    while True:
        try:
            msg = await websocket.recv()
        except websockets.exceptions.ConnectionClosedOK:
            logger.info("connection closed normally")
            break
        except websockets.exceptions.WebSocketException as exc:
            logger.error(
                "websocket error while receiving updates: %s",
                _describe_ws_exception(exc),
            )
            raise RuntimeError("Transcription service websocket error") from exc

        parsed = _parse_ws_message(msg)
        match parsed:
            case None:
                continue
            case WLKMessageStatus(status="active_transcription") as message:
                last_active_transcription = message
                if backpressure is not None:
                    backpressure.update_server_progress(
                        _current_time_from_status(message)
                    )
            case WLKMessageReadyToStopMessage():
                break

    return last_active_transcription


async def transcribe_audio_bytes(payload: bytes) -> WLKMessageStatus | None:
    """
    Transcribes audio bytes by streaming them to a WebSocket transcription service and receiving updates.

    Args:
        payload (bytes): The audio data to be transcribed.

    Raises:
        RuntimeError: If there is an error with the transcription service.

    Returns:
        WLKMessageStatus | None: The last active transcription status received from the transcription service,
            or None if no active transcription was received.
    """
    ws_uri = settings.TRANSCRIBE_WS_URI

    if not ws_uri:
        raise RuntimeError("TRANSCRIBE_WS_URI is not configured")

    logger.info("streaming audio for transcription")

    ping_interval = settings.TRANSCRIBE_WS_PING_INTERVAL_SECONDS or None
    ping_timeout = settings.TRANSCRIBE_WS_PING_TIMEOUT_SECONDS or None
    backpressure = _Backpressure(
        lead_budget_s=float(settings.TRANSCRIBE_WS_LEAD_BUDGET_SECONDS),
        initial_grace_s=float(settings.TRANSCRIBE_WS_LEAD_INITIAL_GRACE_SECONDS),
    )

    try:
        async with websockets.connect(
            ws_uri, ping_interval=ping_interval, ping_timeout=ping_timeout
        ) as websocket:
            receive_task = asyncio.create_task(
                _receive_updates(websocket, backpressure)
            )
            try:
                total_bytes = await _stream_audio_bytes(
                    payload, websocket, backpressure
                )
                await websocket.send(b"")
                logger.info("sent %s bytes to transcription service", total_bytes)
                last_active_transcription = await receive_task
            except Exception:
                if not receive_task.done():
                    receive_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await receive_task
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

    backpressure = _Backpressure(
        lead_budget_s=float(settings.TRANSCRIBE_WS_LEAD_BUDGET_SECONDS),
        initial_grace_s=float(settings.TRANSCRIBE_WS_LEAD_INITIAL_GRACE_SECONDS),
    )

    streaming_task: asyncio.Task | None = None
    decoded = await asyncio.to_thread(_decode_audio, payload)
    total_time = decoded.duration_s
    try:
        async with websockets.connect(
            ws_uri, ping_interval=ping_interval, ping_timeout=ping_timeout
        ) as websocket:
            streaming_task = asyncio.create_task(
                _stream_and_signal_end(decoded, websocket, backpressure)
            )
            while True:
                try:
                    msg = await websocket.recv()
                except websockets.exceptions.ConnectionClosedOK:
                    logger.info("connection closed normally")
                    break
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
                        current_time = _current_time_from_status(message)
                        # Feed the server's progress into the backpressure
                        # controller so the send loop knows how far it can
                        # safely get ahead.
                        backpressure.update_server_progress(current_time)
                        yield ASRStreamChunk(
                            paragraphs=lines_to_paragraphs(message.lines),
                            current_time=current_time,
                            total_time=total_time,
                        )
                    case WLKMessageReadyToStopMessage():
                        break
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
    backpressure: _Backpressure | None = None,
) -> None:
    """Stream audio bytes then send the empty end-of-stream marker."""
    total_bytes = await _stream_audio_bytes(payload, websocket, backpressure)
    await websocket.send(b"")
    logger.info("sent %s bytes to transcription service", total_bytes)
