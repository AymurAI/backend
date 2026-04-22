import asyncio
import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from aymurai.api.meta.asr.websocket import WLKMessageTranscriptionLine
from aymurai.audio.asr_client import (
    _DecodedAudio,
    lines_to_paragraphs,
    transcribe_audio_bytes_stream,
)


class FakeWS:
    """Minimal async context manager mimicking websockets.connect."""

    def __init__(self, incoming_messages: list[str]):
        self._incoming = list(incoming_messages)
        self.sent: list[bytes] = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True
        return False

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        await asyncio.sleep(0)  # yield to event loop so other tasks can run
        if not self._incoming:
            # Signal normal closure
            import websockets.exceptions

            raise websockets.exceptions.ConnectionClosedOK(None, None)
        return self._incoming.pop(0)


def _active_msg(speaker: int, text: str, start: float, end: float) -> str:
    return json.dumps(
        {
            "status": "active_transcription",
            "lines": [
                {
                    "speaker": speaker,
                    "text": text,
                    "start": start,
                    "end": end,
                }
            ],
            "buffer_transcription": "",
            "buffer_diarization": "",
            "buffer_translation": "",
            "remaining_time_transcription": 0.0,
            "remaining_time_diarization": 0.0,
            "speaker_ids": {},
        }
    )


def _ready_to_stop_msg() -> str:
    return json.dumps({"type": "ready_to_stop"})


def test_should_map_ws_lines_to_paragraphs_when_given_transcription_lines():
    lines = [
        WLKMessageTranscriptionLine(
            speaker=0,
            text="hola",
            start=timedelta(seconds=0),
            end=timedelta(seconds=1),
        ),
        WLKMessageTranscriptionLine(
            speaker=3,
            text="mundo",
            start=timedelta(seconds=1),
            end=timedelta(seconds=2),
        ),
    ]

    result = lines_to_paragraphs(lines)

    assert len(result) == 2
    assert result[0].speaker_no == 0
    assert result[0].text == "hola"
    assert result[0].start == timedelta(seconds=0)
    assert result[0].end == timedelta(seconds=1)
    assert result[1].speaker_no == 3
    assert result[1].text == "mundo"
    assert result[1].start == timedelta(seconds=1)
    assert result[1].end == timedelta(seconds=2)


def test_should_return_empty_list_when_given_empty_lines():
    result = lines_to_paragraphs([])
    assert result == []


@pytest.mark.asyncio
async def test_should_yield_paragraphs_per_status_when_streaming():
    fake_ws = FakeWS(
        incoming_messages=[
            _active_msg(0, "hola", 0.0, 1.0),
            _active_msg(0, "hola mundo", 0.0, 2.0),
            _ready_to_stop_msg(),
        ]
    )

    # Patch websockets.connect to return our fake ws
    with (
        patch("aymurai.audio.asr_client.websockets.connect", return_value=fake_ws),
        patch(
            "aymurai.audio.asr_client._stream_audio_bytes",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "aymurai.audio.asr_client._decode_audio",
            return_value=_DecodedAudio(array=np.zeros(0), duration_s=2.0),
        ),
        patch(
            "aymurai.audio.asr_client.settings.TRANSCRIBE_WS_URI",
            "ws://fake/ws",
        ),
    ):
        snapshots = []
        async for chunk in transcribe_audio_bytes_stream(b"fake-audio"):
            snapshots.append(chunk)

    assert len(snapshots) == 2
    assert snapshots[0].paragraphs[0].text == "hola"
    assert snapshots[1].paragraphs[0].text == "hola mundo"
    # total_time comes from the mocked duration probe
    assert snapshots[0].total_time == 2.0
    assert snapshots[1].total_time == 2.0
    # current_time reflects the last line's end timestamp in seconds
    assert snapshots[0].current_time == 1.0
    assert snapshots[1].current_time == 2.0


@pytest.mark.asyncio
async def test_should_raise_runtime_error_when_ws_uri_not_configured():
    with patch("aymurai.audio.asr_client.settings.TRANSCRIBE_WS_URI", None):
        gen = transcribe_audio_bytes_stream(b"data")
        with pytest.raises(RuntimeError, match="TRANSCRIBE_WS_URI is not configured"):
            await gen.__anext__()


@pytest.mark.asyncio
async def test_should_cleanup_streaming_task_when_caller_cancels():
    fake_ws = FakeWS(
        incoming_messages=[
            _active_msg(0, "hola", 0.0, 1.0),
        ]
        # never-ending: no ready_to_stop, recv will block forever after
    )

    stream_calls = []

    async def slow_stream(_payload, _ws, _backpressure=None):
        stream_calls.append("started")
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            stream_calls.append("cancelled")
            raise
        return 0

    with (
        patch("aymurai.audio.asr_client.websockets.connect", return_value=fake_ws),
        patch("aymurai.audio.asr_client._stream_audio_bytes", new=slow_stream),
        patch(
            "aymurai.audio.asr_client._decode_audio",
            return_value=_DecodedAudio(array=np.zeros(0), duration_s=1.0),
        ),
        patch("aymurai.audio.asr_client.settings.TRANSCRIBE_WS_URI", "ws://fake/ws"),
    ):
        gen = transcribe_audio_bytes_stream(b"data")
        first = await gen.__anext__()
        assert first.paragraphs[0].text == "hola"
        await gen.aclose()

    assert "started" in stream_calls
    assert "cancelled" in stream_calls
