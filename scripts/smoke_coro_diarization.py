#!/usr/bin/env python
"""Diarization smoke test against an already-running coro ASR server.

Unlike ``scripts/smoke_coro.py`` (which boots its own server), this script
assumes a coro server is already up and focuses on verifying that speaker
diarization is correctly wired end-to-end through aymurai's client. It feeds a
30s+ multi-speaker clip and asserts:

1. the audio is at least ``SMOKE_MIN_DURATION`` seconds long;
2. the client returns speaker-attributed segments;
3. at least two distinct speakers are detected (diarization is active);
4. every segment is well-formed (start < end, non-empty speaker);
5. the segments cover a reasonable fraction of the audio.

Usage:
    rtk uv run python scripts/smoke_coro_diarization.py /path/to/audio.wav

Env overrides:
    TRANSCRIBE_BASE_URL   coro base URL (default: http://localhost:${CORO_PORT}/v1)
    CORO_PORT             port if TRANSCRIBE_BASE_URL is unset (default 8000)
    TRANSCRIBE_API_KEY    forwarded to the client (default "not-needed")
    SMOKE_AUDIO           audio path if not passed as argv[1]
    SMOKE_MIN_DURATION    minimum required duration in seconds (default 30)
    SMOKE_MIN_COVERAGE    min fraction of audio covered by segments (default 0.5)
"""

from __future__ import annotations

import asyncio
import mimetypes
import os
import sys
from pathlib import Path


def log(msg: str) -> None:
    print(f"[diar-smoke] {msg}", flush=True)


def resolve_base_url() -> str:
    base_url = os.environ.get("TRANSCRIBE_BASE_URL")
    if base_url:
        return base_url
    port = os.environ.get("CORO_PORT", "8000")
    return f"http://localhost:{port}/v1"


def resolve_audio() -> Path:
    raw = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SMOKE_AUDIO")
    if not raw:
        raise SystemExit(
            "no audio provided: pass a path as the first argument or set SMOKE_AUDIO"
        )
    path = Path(raw).expanduser()
    if not path.exists():
        raise SystemExit(f"audio file not found: {path}")
    return path


def content_type_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def main() -> int:
    min_duration = float(os.environ.get("SMOKE_MIN_DURATION", "30"))
    min_coverage = float(os.environ.get("SMOKE_MIN_COVERAGE", "0.5"))

    audio = resolve_audio()
    base_url = resolve_base_url()
    os.environ["TRANSCRIBE_BASE_URL"] = base_url
    os.environ.setdefault("TRANSCRIBE_API_KEY", "not-needed")

    # Imports happen after env is set so settings pick up the base URL.
    from aymurai.audio.asr_client import transcribe_audio_bytes
    from aymurai.audio.duration import probe_audio_duration

    payload = audio.read_bytes()
    log(f"audio: {audio} ({len(payload)} bytes)")
    log(f"coro base URL: {base_url}")

    duration = probe_audio_duration(payload)
    if duration is None:
        log("WARNING: could not probe duration (ffprobe missing?); skipping check")
    else:
        log(f"audio duration: {duration:.1f}s (minimum required: {min_duration:.0f}s)")
        if duration < min_duration:
            log(f"FAILED: audio is shorter than {min_duration:.0f}s")
            return 1

    log("transcribing via aymurai transcribe_audio_bytes ...")
    segments = asyncio.run(
        transcribe_audio_bytes(payload, audio.name, content_type_for(audio))
    )

    if not segments:
        log("FAILED: client returned no segments")
        return 1

    malformed = [s for s in segments if not s.speaker or s.end < s.start or s.start < 0]
    if malformed:
        log(f"FAILED: {len(malformed)} malformed segment(s); first: {malformed[0]!r}")
        return 1

    zero_length = [s for s in segments if s.end == s.start]
    if zero_length:
        log(f"note: {len(zero_length)} zero-length segment(s) (start == end), allowed")

    speakers = sorted({s.speaker for s in segments})
    spoken = sum(s.end - s.start for s in segments)
    span_end = max(s.end for s in segments)
    coverage = (span_end / duration) if duration else None

    log(f"received {len(segments)} segment(s) across {len(speakers)} speaker(s)")
    for speaker in speakers:
        spk_segs = [s for s in segments if s.speaker == speaker]
        spk_time = sum(s.end - s.start for s in spk_segs)
        log(f"  speaker {speaker}: {len(spk_segs)} segment(s), {spk_time:.1f}s")
    log(f"total spoken time: {spoken:.1f}s ; last segment ends at {span_end:.1f}s")

    log("--- transcript (first 12 segments) ---")
    for seg in segments[:12]:
        log(f"  [{seg.start:6.2f}-{seg.end:6.2f}] spk {seg.speaker}: {seg.text}")
    if len(segments) > 12:
        log(f"  ... ({len(segments) - 12} more)")

    if len(speakers) < 2:
        log(
            "FAILED: only one speaker detected — diarization does not appear wired "
            "(expected >= 2 distinct speakers in a multi-speaker clip)"
        )
        return 1

    if coverage is not None:
        log(f"segment coverage: {coverage:.0%} of audio (minimum {min_coverage:.0%})")
        if coverage < min_coverage:
            log("FAILED: segments cover too little of the audio")
            return 1

    log("DIARIZATION SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
