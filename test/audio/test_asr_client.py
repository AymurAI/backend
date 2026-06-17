import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aymurai.api.meta.asr.coro import CoroSegment
from aymurai.audio.asr_client import transcribe_audio_bytes
from aymurai.settings import settings


class _FakeEvent:
    def __init__(self, type: str, text: str | None = None):
        self.type = type
        self.text = text


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
