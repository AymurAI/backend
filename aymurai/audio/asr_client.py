import json
from collections.abc import AsyncGenerator

from openai import APIConnectionError, APIError, AsyncOpenAI

from aymurai.api.meta.asr.coro import (
    CoroSegment,
    CoroStreamDelta,
    CoroStreamEvent,
    CoroStreamSegments,
)
from aymurai.logger import get_logger
from aymurai.settings import settings

logger = get_logger(__name__)

DONE_EVENT_TYPE = "transcript.text.done"
DELTA_EVENT_TYPE = "transcript.text.delta"


async def transcribe_audio_bytes(
    payload: bytes,
    filename: str,
    content_type: str,
) -> list[CoroSegment]:
    """
    Transcribe audio by streaming it to the coro server over SSE.

    Sends the audio to coro's OpenAI-compatible ``/v1/audio/transcriptions``
    endpoint with ``stream=True`` and parses the ``transcript.text.done`` frame.

    Args:
        payload (bytes): The raw audio file bytes (any ffmpeg-decodable format).
        filename (str): The uploaded file name (used for the multipart part).
        content_type (str): The uploaded file MIME type.

    Raises:
        RuntimeError: If the base URL is unset, the service errors, or no done
            frame is received.

    Returns:
        list[CoroSegment]: The speaker-attributed transcription segments.
    """
    base_url = settings.TRANSCRIBE_BASE_URL
    if not base_url:
        raise RuntimeError("TRANSCRIBE_BASE_URL is not configured")

    client = AsyncOpenAI(base_url=base_url, api_key=settings.TRANSCRIBE_API_KEY)

    logger.info("streaming audio to coro for transcription")
    try:
        stream = await client.audio.transcriptions.create(
            file=(filename, payload, content_type),
            model="whisper-1",
            language="es",
            stream=True,
            response_format="diarized_json",
        )
        async for event in stream:
            if event.type == DONE_EVENT_TYPE:
                data = json.loads(event.text)
                return [
                    CoroSegment.model_validate(segment)
                    for segment in data.get("segments", [])
                ]
    except (APIError, APIConnectionError) as exc:
        logger.error("coro transcription error: %s", exc)
        raise RuntimeError("Transcription service error") from exc

    raise RuntimeError("coro stream ended without a done frame")


async def stream_transcribe_audio_bytes(
    payload: bytes,
    filename: str,
    content_type: str,
) -> AsyncGenerator[CoroStreamEvent, None]:
    """
    Stream a transcription from coro, yielding deltas then the final segments.

    Sends the audio to coro's OpenAI-compatible ``/v1/audio/transcriptions``
    endpoint with ``stream=True``. Yields one ``CoroStreamDelta`` per
    ``transcript.text.delta`` event as text arrives, then a single
    ``CoroStreamSegments`` parsed from the ``transcript.text.done`` frame.

    Args:
        payload (bytes): The raw audio file bytes (any ffmpeg-decodable format).
        filename (str): The uploaded file name (used for the multipart part).
        content_type (str): The uploaded file MIME type.

    Raises:
        RuntimeError: If the base URL is unset, the service errors, or no done
            frame is received.

    Yields:
        CoroStreamEvent: Incremental deltas followed by the final segments.
    """
    base_url = settings.TRANSCRIBE_BASE_URL
    if not base_url:
        raise RuntimeError("TRANSCRIBE_BASE_URL is not configured")

    client = AsyncOpenAI(base_url=base_url, api_key=settings.TRANSCRIBE_API_KEY)

    logger.info("streaming audio to coro for transcription (sse)")
    try:
        stream = await client.audio.transcriptions.create(
            file=(filename, payload, content_type),
            model="whisper-1",
            language="es",
            stream=True,
            response_format="diarized_json",
        )
        async for event in stream:
            if event.type == DELTA_EVENT_TYPE:
                yield CoroStreamDelta(text=event.delta or "")
            elif event.type == DONE_EVENT_TYPE:
                data = json.loads(event.text)
                yield CoroStreamSegments(
                    segments=[
                        CoroSegment.model_validate(segment)
                        for segment in data.get("segments", [])
                    ]
                )
                return
    except (APIError, APIConnectionError) as exc:
        logger.error("coro transcription error: %s", exc)
        raise RuntimeError("Transcription service error") from exc

    raise RuntimeError("coro stream ended without a done frame")
