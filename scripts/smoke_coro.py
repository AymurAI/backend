#!/usr/bin/env python
"""Smoke test for the coro ASR integration.

Starts the coro server (via ``scripts/run-coro.sh``), waits for it to become
healthy, then transcribes a sample audio file over the OpenAI-compatible SSE
endpoint two ways:

1. directly with the ``openai`` SDK (``stream=True``) — shows the raw SSE events;
2. through aymurai's own client ``transcribe_audio_bytes`` — proves the wiring.

Usage:
    rtk uv run python scripts/smoke_coro.py [cpu|gpu]

Env overrides:
    CORO_PORT          (default 8000)
    SMOKE_AUDIO        path to a local audio file (default: download sample)
    SMOKE_AUDIO_URL    sample to download if SMOKE_AUDIO is absent
    SMOKE_HEALTH_TIMEOUT  seconds to wait for /health (default 1200)
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORO_LOG = Path("/tmp/coro-smoke.log")
MODE = sys.argv[1] if len(sys.argv) > 1 else "cpu"
PORT = os.environ.get("CORO_PORT", "8000")
BASE_URL = f"http://localhost:{PORT}/v1"
HEALTH_URL = f"http://localhost:{PORT}/health"
HEALTH_TIMEOUT = int(os.environ.get("SMOKE_HEALTH_TIMEOUT", "1200"))
AUDIO_PATH = Path(
    os.environ.get("SMOKE_AUDIO", str(REPO_ROOT / "resources/cache/smoke/sample.wav"))
)
AUDIO_URL = os.environ.get(
    "SMOKE_AUDIO_URL",
    "https://google-research.github.io/lingvo-lab/translatotron/fisher_src/775.wav",
)


def log(msg: str) -> None:
    print(f"[smoke] {msg}", flush=True)


def ensure_audio() -> Path:
    if AUDIO_PATH.exists():
        log(f"using existing audio: {AUDIO_PATH}")
        return AUDIO_PATH
    AUDIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    log(f"downloading sample audio: {AUDIO_URL}")
    urllib.request.urlretrieve(AUDIO_URL, AUDIO_PATH)  # noqa: S310
    log(f"saved sample audio: {AUDIO_PATH} ({AUDIO_PATH.stat().st_size} bytes)")
    return AUDIO_PATH


def start_coro() -> subprocess.Popen:
    log(f"starting coro ({MODE}) on port {PORT} ; logs -> {CORO_LOG}")
    logfh = CORO_LOG.open("w")
    return subprocess.Popen(
        ["bash", str(REPO_ROOT / "scripts/run-coro.sh"), MODE],
        cwd=REPO_ROOT,
        stdout=logfh,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def wait_healthy(proc: subprocess.Popen) -> None:
    log(f"waiting for {HEALTH_URL} (timeout {HEALTH_TIMEOUT}s) ...")
    deadline = time.time() + HEALTH_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("coro process exited before becoming healthy")
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=5) as resp:  # noqa: S310
                if resp.status == 200:
                    log("coro is healthy")
                    return
        except Exception:
            pass
        time.sleep(3)
    raise TimeoutError("coro did not become healthy in time")


def transcribe_with_sdk(audio: Path) -> None:
    from openai import OpenAI

    log("=== SSE transcription via openai SDK (stream=True) ===")
    client = OpenAI(base_url=BASE_URL, api_key="not-needed")
    deltas = 0
    with audio.open("rb") as fh:
        stream = client.audio.transcriptions.create(
            file=fh, model="whisper-1", language="es", stream=True
        )
        for event in stream:
            if event.type == "transcript.text.delta":
                deltas += 1
            elif event.type == "transcript.text.done":
                payload = json.loads(event.text)
                segments = payload.get("segments", [])
                log(f"received {deltas} delta events, {len(segments)} segments")
                for seg in segments:
                    log(
                        f"  [{seg['start']:.2f}-{seg['end']:.2f}] "
                        f"speaker {seg['speaker']}: {seg['text']}"
                    )


def transcribe_with_aymurai_client(audio: Path) -> None:
    os.environ["TRANSCRIBE_BASE_URL"] = BASE_URL
    from aymurai.audio.asr_client import transcribe_audio_bytes

    log("=== transcription via aymurai transcribe_audio_bytes ===")
    payload = audio.read_bytes()
    segments = asyncio.run(transcribe_audio_bytes(payload, audio.name, "audio/wav"))
    log(f"aymurai client returned {len(segments)} CoroSegment(s)")
    for seg in segments:
        log(f"  speaker {seg.speaker} [{seg.start:.2f}-{seg.end:.2f}]: {seg.text}")


def main() -> int:
    audio = ensure_audio()
    proc = start_coro()
    try:
        wait_healthy(proc)
        transcribe_with_sdk(audio)
        transcribe_with_aymurai_client(audio)
        log("SMOKE TEST PASSED")
        return 0
    except Exception as exc:  # noqa: BLE001
        log(f"SMOKE TEST FAILED: {exc}")
        if CORO_LOG.exists():
            log(f"--- {CORO_LOG} tail ---")
            print("\n".join(CORO_LOG.read_text().splitlines()[-40:]), flush=True)
        return 1
    finally:
        if proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except Exception:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


if __name__ == "__main__":
    raise SystemExit(main())
