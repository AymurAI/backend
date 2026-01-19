import asyncio
import contextlib
import io
import json

import librosa
import numpy as np
import websockets
from fastapi import HTTPException, UploadFile
from fastapi.routing import APIRouter
from pydantic import TypeAdapter, ValidationError
from starlette import status

from aymurai.api.meta.asr.websocket import (
    TranscriptionItem,
    WLKMessageRawResponse,
    WLKMessageReadyToStopMessage,
    WLKMessageStatus,
)
from aymurai.logger import get_logger
from aymurai.settings import settings

logger = get_logger(__name__)

router = APIRouter()

SAMPLE_RATE_HZ = 16000
CHUNK_SECONDS = 1
CHUNK_SAMPLES = SAMPLE_RATE_HZ * CHUNK_SECONDS
MAX_WS_LOG_CHARS = 2000
ASR_RAW_RESPONSE_ADAPTER = TypeAdapter(WLKMessageRawResponse)


async def _stream_audio(
    file: UploadFile,
    websocket: websockets.ClientConnection,
) -> int:
    payload = await file.read()
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
        logger.warning(f"received non-json websocket payload: {payload_preview}")
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
            logger.error(f"websocket error while receiving updates: {exc}")
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


@router.post("/transcribe", response_model=list[TranscriptionItem])
async def transcribe(file: UploadFile) -> list[TranscriptionItem]:
    """
    Stream an uploaded audio file to an external websocket transcription service.
    """
    if not settings.TRANSCRIBE_WS_URI:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="TRANSCRIBE_WS_URI is not configured",
        )

    logger.info("streaming audio for transcription")

    try:
        async with websockets.connect(settings.TRANSCRIBE_WS_URI) as websocket:
            receive_task = asyncio.create_task(_receive_updates(websocket))
            try:
                total_bytes = await _stream_audio(file, websocket)
                await websocket.send(b"")
                logger.info(f"sent {total_bytes} bytes to transcription service")
                last_active_transcription = await receive_task
            except Exception:
                if not receive_task.done():
                    receive_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await receive_task
                raise
    except websockets.exceptions.WebSocketException as exc:
        logger.error(f"websocket error during transcription: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Transcription service websocket error",
        ) from exc
    except Exception as exc:
        logger.error(f"unexpected error during transcription: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error during transcription",
        ) from exc

    if not last_active_transcription:
        return []

    return [
        TranscriptionItem(
            speaker_no=line.speaker,
            speaker_id=line.speaker_id or f"speaker-{line.speaker}",
            start=line.start,
            end=line.end,
            text=line.text,
        )
        for line in last_active_transcription.lines
    ]
