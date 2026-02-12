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
    payload = path.read_bytes()
    return asyncio.run(transcribe_audio_bytes(payload))
