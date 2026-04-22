import asyncio
import contextlib
import io
import json
from pathlib import Path
from typing import AsyncGenerator, NamedTuple

import librosa
import numpy as np
import websockets
from pydantic import TypeAdapter, ValidationError

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

    Why this exists
    ---------------
    The upstream WhisperLiveKit server runs on uvicorn with a bounded
    WebSocket frame queue (``ws_max_queue`` defaults to 32 frames) and
    its app consumes frames at real-time audio pace inside
    ``process_audio(message)``. If we push audio faster than the server
    consumes it, the queue fills up, the server's frame reader task
    blocks on ``ASGIqueue.put()``, and our PING control frames sitting
    in the TCP buffer behind queued BINARY frames never get seen in
    time. Our ``websockets`` client then hits ``ping_timeout`` waiting
    for a Pong that never comes, and closes the connection with 1011.

    Design
    ------
    We cap how far *ahead* of the server's progress we are allowed to
    be. "Progress" is the larger of:

    1. ``server_current_time_s`` \u2014 the ``end`` timestamp of the last
       transcription line the server has reported, which is a concrete
       signal that those seconds of audio have been fully processed.
    2. ``wallclock_elapsed_s - INITIAL_GRACE`` \u2014 a wall-clock fallback
       that advances during silence stretches when the server stops
       emitting ``active_transcription`` messages. This keeps the
       pacer from deadlocking when upstream goes quiet mid-audio.

    ``lead_s = audio_sent_s - effective_progress_s`` must stay <=
    ``lead_budget_s``. When the lead exceeds the budget, the send loop
    pauses until recv updates ``server_current_time`` or wall-clock
    catches up.

    Attributes:
        lead_budget_s: Maximum seconds of audio we're allowed to be
            ahead of the server's effective progress.
        initial_grace_s: Headroom we allow at the start before the
            wall-clock fallback starts pushing back. Also effectively
            the "catch-up" factor during silence gaps.
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
    """
    Render a WebSocket exception with as much structured detail as possible.

    For :class:`websockets.exceptions.ConnectionClosed` (and its subclasses
    ``ConnectionClosedOK`` / ``ConnectionClosedError``), this surfaces the
    close ``code`` and ``reason`` from both the frame the peer sent
    (``rcvd``) and the frame we sent (``sent``). This is the signal needed
    to distinguish e.g. an upstream server crash (1011) from a client-side
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


class ASRStreamChunk(NamedTuple):
    """A single snapshot yielded by :func:`transcribe_audio_bytes_stream`.

    Attributes:
        paragraphs: Cumulative list of transcribed paragraphs so far.
        current_time: Seconds of audio covered by the transcription so far
            (``end`` timestamp of the last line), or ``None`` if no lines exist.
        total_time: Estimated total audio duration in seconds
            (``current_time + remaining_time_transcription`` from the upstream
            service), or ``None`` if ``current_time`` is ``None``.
    """

    paragraphs: list[ASRParagraph]
    current_time: float | None
    total_time: float | None


def _audio_duration_seconds(payload: bytes) -> float:
    """Return the duration of an audio payload in seconds at SAMPLE_RATE_HZ.

    Synchronous: call via :func:`asyncio.to_thread` from async contexts to
    avoid blocking the event loop during decode.
    """
    audio, _ = librosa.load(io.BytesIO(payload), sr=SAMPLE_RATE_HZ, mono=True)
    return len(audio) / SAMPLE_RATE_HZ


def _current_time_from_status(message: WLKMessageStatus) -> float | None:
    """Return the end timestamp of the last transcription line in seconds, or None."""
    if not message.lines:
        return None
    return message.lines[-1].end.total_seconds()


def lines_to_paragraphs(
    lines: list[WLKMessageTranscriptionLine],
) -> list[ASRParagraph]:
    """
    Map WebSocket transcription lines to ASRParagraph objects.

    Args:
        lines (list[WLKMessageTranscriptionLine]): Transcription lines from the ASR service.

    Returns:
        list[ASRParagraph]: ASRParagraph objects ready for serialization or storage.
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


def _decode_audio(payload: bytes) -> np.ndarray:
    """Decode an audio payload to a mono float32 array at SAMPLE_RATE_HZ.

    Pure CPU/IO work — kept as a plain sync function so callers can offload it
    to a worker thread via :func:`asyncio.to_thread` and avoid blocking the
    event loop (which would starve WebSocket keepalives and SSE keepalives).
    """
    audio, _ = librosa.load(io.BytesIO(payload), sr=SAMPLE_RATE_HZ, mono=True)
    return audio


async def _stream_audio_bytes(
    payload: bytes,
    websocket: websockets.ClientConnection,
    backpressure: "_Backpressure | None" = None,
) -> int:
    """Stream audio bytes to a WebSocket connection in chunks.

    If ``backpressure`` is supplied, pause between chunks whenever the
    upstream ASR service's transcription backlog grows past the configured
    high-water mark. This prevents saturating the server's WebSocket frame
    queue, which would otherwise starve control-frame handling and cause
    1011 "keepalive ping timeout" closes.

    Args:
        payload: The audio data to be streamed.
        websocket: The WebSocket connection to stream the audio data to.
        backpressure: Optional adaptive pacer fed by the recv loop. When
            ``None``, sends at maximum TCP-permitted rate (legacy behavior).

    Returns:
        int: The total number of bytes sent to the WebSocket.
    """
    # Offload the CPU-bound decode to a worker thread so the event loop can
    # keep servicing recv() / respond to server pings during decoding.
    audio = await asyncio.to_thread(_decode_audio, payload)
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
) -> WLKMessageStatus | None:
    """
    Receives updates from the WebSocket connection and returns the last active transcription status.

    Args:
        websocket (websockets.ClientConnection): The WebSocket connection to receive updates from.

    Returns:
        WLKMessageStatus | None: The last active transcription status,
            or None if no active transcription was received.
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
            break

        parsed = _parse_ws_message(msg)
        match parsed:
            case None:
                continue
            case WLKMessageStatus(status="active_transcription") as message:
                last_active_transcription = message
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
    """
    Stream transcription updates from the ASR WebSocket service.

    Yields an :class:`ASRStreamChunk` for each intermediate active_transcription
    update received from the upstream service. Each chunk contains a cumulative
    paragraph snapshot and progress information (current_time / total_time in
    seconds). The generator terminates when the service sends a ready_to_stop
    message or the connection closes normally.

    Args:
        payload (bytes): The audio data to be transcribed.

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

    total_time = await asyncio.to_thread(_audio_duration_seconds, payload)
    ping_interval = settings.TRANSCRIBE_WS_PING_INTERVAL_SECONDS or None
    ping_timeout = settings.TRANSCRIBE_WS_PING_TIMEOUT_SECONDS or None

    # Adaptive backpressure: cap how far ahead of the server's progress we
    # send, so we don't saturate uvicorn's WS frame queue and starve ping/pong
    # handling (which causes 1011 "keepalive ping timeout" closes).
    backpressure = _Backpressure(
        lead_budget_s=float(settings.TRANSCRIBE_WS_LEAD_BUDGET_SECONDS),
        initial_grace_s=float(settings.TRANSCRIBE_WS_LEAD_INITIAL_GRACE_SECONDS),
    )

    streaming_task: asyncio.Task | None = None
    try:
        async with websockets.connect(
            ws_uri, ping_interval=ping_interval, ping_timeout=ping_timeout
        ) as websocket:
            streaming_task = asyncio.create_task(
                _stream_and_signal_end(payload, websocket, backpressure)
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
    payload: bytes,
    websocket: "websockets.ClientConnection",
    backpressure: "_Backpressure | None" = None,
) -> None:
    """Stream audio bytes then send the empty end-of-stream marker."""
    total_bytes = await _stream_audio_bytes(payload, websocket, backpressure)
    await websocket.send(b"")
    logger.info("sent %s bytes to transcription service", total_bytes)


def transcribe_audio_path(path: Path) -> WLKMessageStatus | None:
    """
    Transcribes an audio file at the given path by reading its bytes and sending them to the transcription service.

    Args:
        path (Path): The path to the audio file to be transcribed.

    Returns:
        WLKMessageStatus | None: The last active transcription status received from the transcription service,
            or None if no active transcription was received.
    """
    payload = path.read_bytes()
    return asyncio.run(transcribe_audio_bytes(payload))
