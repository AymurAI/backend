#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-gpu}"
PORT="${CORO_PORT:-8000}"
SPILL_DIR="${CORO_TRANSCRIPT_SPILL_DIR:-./resources/cache/coro-spill}"
mkdir -p "$SPILL_DIR"

export CORO_BACKEND_ASR=onnx-asr
export CORO_MODEL_ASR=nemo-parakeet-tdt-0.6b-v3
export CORO_BACKEND_DIARIZATION=nemo
export CORO_PIPELINE=streaming
export CORO_TRANSCRIPT_SPILL_DIR="$SPILL_DIR"

case "$MODE" in
  gpu)
    export CORO_ASR_DEVICE=cuda
    export CORO_DIARIZATION_DEVICE=cuda
    EXTRA="cuda"
    ;;
  cpu)
    export CORO_ASR_DEVICE=cpu
    export CORO_ASR_QUANTIZATION=int8
    export CORO_DIARIZATION_DEVICE=cpu
    EXTRA="cpu"
    ;;
  *)
    echo "usage: $0 [cpu|gpu]" >&2
    exit 2
    ;;
esac

exec uvx --from "coro[$EXTRA] @ git+https://github.com/collectiveai-team/coro" \
  coro --port "$PORT"
