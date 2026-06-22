import subprocess
import tempfile

from aymurai.logger import get_logger

logger = get_logger(__name__)

_FFPROBE_ARGS = [
    "ffprobe",
    "-v",
    "error",
    "-show_entries",
    "format=duration",
    "-of",
    "default=noprint_wrappers=1:nokey=1",
]

_FFPROBE_TIMEOUT_SECONDS = 30


def probe_audio_duration(payload: bytes) -> float | None:
    """
    Probe the duration of an audio payload in seconds using ffprobe.

    The bytes are written to a temporary file because ffprobe cannot read the
    duration of container formats (e.g. WAV) from a non-seekable stdin pipe. Any
    failure (missing ffprobe, undecodable input, timeout, non-numeric output) is
    treated as "unknown" and returns None so callers can degrade gracefully.

    Args:
        payload (bytes): The raw audio file bytes.

    Returns:
        float | None: The duration in seconds, or None if it cannot be determined.
    """
    if not payload:
        return None

    try:
        with tempfile.NamedTemporaryFile(suffix=".audio") as handle:
            handle.write(payload)
            handle.flush()
            result = subprocess.run(
                [*_FFPROBE_ARGS, handle.name],
                capture_output=True,
                timeout=_FFPROBE_TIMEOUT_SECONDS,
                check=True,
            )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("ffprobe duration probe failed: %s", exc)
        return None

    raw = result.stdout.decode("utf-8", errors="ignore").strip()
    try:
        duration = float(raw)
    except ValueError:
        return None

    return duration if duration > 0 else None
