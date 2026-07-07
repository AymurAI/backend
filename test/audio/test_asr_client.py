import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIConnectionError

from aymurai.api.meta.asr.coro import (
    CoroSegment,
    CoroStreamDelta,
    CoroStreamSegments,
)
from aymurai.audio.asr_client import (
    stream_transcribe_audio_bytes,
    transcribe_audio_bytes,
)
from aymurai.settings import settings


class _FakeEvent:
    def __init__(self, type: str, text: str | None = None, delta: str | None = None):
        self.type = type
        self.text = text
        self.delta = delta


async def _collect(agen):
    return [item async for item in agen]


class _FakeStream:
    def __init__(self, events):
        self._events = events

    def __aiter__(self):
        async def _gen():
            for event in self._events:
                yield event

        return _gen()


def _patched_client(events):
    create = AsyncMock(return_value=_FakeStream(events))
    client = MagicMock()
    client.audio.transcriptions.create = create
    return patch("aymurai.audio.asr_client.AsyncOpenAI", return_value=client)


def test_should_return_segments_when_done_frame_received(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_BASE_URL", "http://coro.local/v1")
    done_text = json.dumps(
        {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hola", "speaker": "1"},
                {"start": 1.0, "end": 2.0, "text": "mundo", "speaker": "2"},
            ]
        }
    )
    events = [
        _FakeEvent("transcript.text.delta", None),
        _FakeEvent("transcript.text.done", done_text),
    ]
    with _patched_client(events):
        result = asyncio.run(
            transcribe_audio_bytes(b"audio", "sample.wav", "audio/wav")
        )

    assert result == [
        CoroSegment(start=0.0, end=1.0, text="Hola", speaker="1"),
        CoroSegment(start=1.0, end=2.0, text="mundo", speaker="2"),
    ]


def test_should_raise_when_stream_has_no_done_frame(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_BASE_URL", "http://coro.local/v1")
    events = [_FakeEvent("transcript.text.delta", None)]
    with _patched_client(events):
        with pytest.raises(RuntimeError, match="done frame"):
            asyncio.run(transcribe_audio_bytes(b"audio", "sample.wav", "audio/wav"))


def test_should_raise_when_base_url_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_BASE_URL", None)
    with pytest.raises(RuntimeError, match="not configured"):
        asyncio.run(transcribe_audio_bytes(b"audio", "sample.wav", "audio/wav"))


def test_should_map_openai_connection_error_to_runtime_error(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_BASE_URL", "http://coro.local/v1")
    request = httpx.Request("POST", "http://coro.local/v1/audio/transcriptions")
    create = AsyncMock(side_effect=APIConnectionError(request=request))
    client = MagicMock()
    client.audio.transcriptions.create = create
    with patch("aymurai.audio.asr_client.AsyncOpenAI", return_value=client):
        with pytest.raises(RuntimeError, match="Transcription service error"):
            asyncio.run(transcribe_audio_bytes(b"audio", "sample.wav", "audio/wav"))


# MARK: streaming generator
def test_stream_should_yield_deltas_then_segments(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_BASE_URL", "http://coro.local/v1")
    done_text = json.dumps(
        {
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hola", "speaker": "1"},
            ]
        }
    )
    events = [
        _FakeEvent("transcript.text.delta", delta="Ho"),
        _FakeEvent("transcript.text.delta", delta="la"),
        _FakeEvent("transcript.text.done", text=done_text),
    ]
    with _patched_client(events):
        result = asyncio.run(
            _collect(stream_transcribe_audio_bytes(b"audio", "sample.wav", "audio/wav"))
        )

    assert result == [
        CoroStreamDelta(text="Ho"),
        CoroStreamDelta(text="la"),
        CoroStreamSegments(
            segments=[CoroSegment(start=0.0, end=1.0, text="Hola", speaker="1")]
        ),
    ]


def test_stream_should_stop_after_done_frame(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_BASE_URL", "http://coro.local/v1")
    done_text = json.dumps({"segments": []})
    events = [
        _FakeEvent("transcript.text.done", text=done_text),
        _FakeEvent("transcript.text.delta", delta="ignored"),
    ]
    with _patched_client(events):
        result = asyncio.run(
            _collect(stream_transcribe_audio_bytes(b"audio", "sample.wav", "audio/wav"))
        )

    assert result == [CoroStreamSegments(segments=[])]


def test_stream_should_raise_when_stream_has_no_done_frame(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_BASE_URL", "http://coro.local/v1")
    events = [_FakeEvent("transcript.text.delta", delta="Ho")]
    with _patched_client(events):
        with pytest.raises(RuntimeError, match="done frame"):
            asyncio.run(
                _collect(
                    stream_transcribe_audio_bytes(b"audio", "sample.wav", "audio/wav")
                )
            )


def test_stream_should_raise_when_base_url_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_BASE_URL", None)
    with pytest.raises(RuntimeError, match="not configured"):
        asyncio.run(
            _collect(stream_transcribe_audio_bytes(b"audio", "sample.wav", "audio/wav"))
        )


def test_stream_should_map_connection_error_to_runtime_error(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_BASE_URL", "http://coro.local/v1")
    request = httpx.Request("POST", "http://coro.local/v1/audio/transcriptions")
    create = AsyncMock(side_effect=APIConnectionError(request=request))
    client = MagicMock()
    client.audio.transcriptions.create = create
    with patch("aymurai.audio.asr_client.AsyncOpenAI", return_value=client):
        with pytest.raises(RuntimeError, match="Transcription service error"):
            asyncio.run(
                _collect(
                    stream_transcribe_audio_bytes(b"audio", "sample.wav", "audio/wav")
                )
            )
