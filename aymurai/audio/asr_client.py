import asyncio
import contextlib
import io
import json
from pathlib import Path

import librosa
import numpy as np
import websockets
from pydantic import TypeAdapter, ValidationError

from aymurai.api.meta.asr.websocket import (
    WLKMessageRawResponse,
    WLKMessageReadyToStopMessage,
    WLKMessageStatus,
)
from aymurai.logger import get_logger
from aymurai.settings import settings

logger = get_logger(__name__)

SAMPLE_RATE_HZ = 16000
CHUNK_SECONDS = 1
CHUNK_SAMPLES = SAMPLE_RATE_HZ * CHUNK_SECONDS
MAX_WS_LOG_CHARS = 2000
ASR_RAW_RESPONSE_ADAPTER = TypeAdapter(WLKMessageRawResponse)


async def _stream_audio_bytes(
    payload: bytes,
    websocket: websockets.ClientConnection,
) -> int:
    """
    Streams audio bytes to a WebSocket connection in chunks.

    Args:
        payload (bytes): The audio data to be streamed.
        websocket (websockets.ClientConnection): The WebSocket connection to stream the audio data to.

    Returns:
        int: The total number of bytes sent to the WebSocket.
    """
    audio, _ = librosa.load(io.BytesIO(payload), sr=SAMPLE_RATE_HZ, mono=True)
    total_bytes = 0
    for i in range(0, len(audio), CHUNK_SAMPLES):
        chunk = audio[i : i + CHUNK_SAMPLES]
        if len(chunk) == 0:
            continue
        chunk_int16 = (chunk * 32768).astype(np.int16)
        data = chunk_int16.tobytes()
        total_bytes += len(data)
        await websocket.send(data)
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
            logger.error("websocket error while receiving updates: %s", exc)
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

    try:
        async with websockets.connect(ws_uri) as websocket:
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
        logger.error("websocket error during transcription: %s", exc)
        raise RuntimeError("Transcription service websocket error") from exc
    except Exception as exc:
        logger.error("unexpected error during transcription: %s", exc)
        raise RuntimeError("Unexpected error during transcription") from exc

    return last_active_transcription


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
