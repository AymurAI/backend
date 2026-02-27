import io
import math
import struct
import wave

import pytest


@pytest.fixture
def make_wav_bytes():
    def _build(
        duration_seconds: float = 1.0,
        sample_rate: int = 16000,
        freq_hz: float = 440.0,
    ) -> bytes:
        frame_count = int(duration_seconds * sample_rate)
        pcm = bytearray()
        for i in range(frame_count):
            sample = int(
                32767 * 0.2 * math.sin(2 * math.pi * freq_hz * (i / sample_rate))
            )
            pcm.extend(struct.pack("<h", sample))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(bytes(pcm))

        return buffer.getvalue()

    return _build
