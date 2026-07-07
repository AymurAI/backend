import io
import math
import struct
import wave

from aymurai.audio.duration import probe_audio_duration


def _make_wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    frame_count = int(duration_seconds * sample_rate)
    pcm = bytearray()
    for i in range(frame_count):
        sample = int(32767 * 0.2 * math.sin(2 * math.pi * 440.0 * (i / sample_rate)))
        pcm.extend(struct.pack("<h", sample))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(pcm))

    return buffer.getvalue()


def test_should_return_duration_in_seconds_for_valid_wav():
    payload = _make_wav_bytes(duration_seconds=2.0)

    duration = probe_audio_duration(payload)

    assert duration is not None
    assert abs(duration - 2.0) < 0.05


def test_should_return_none_for_non_audio_bytes():
    assert probe_audio_duration(b"not audio at all") is None


def test_should_return_none_for_empty_payload():
    assert probe_audio_duration(b"") is None
