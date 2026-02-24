from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_documents_manifest(paths: list[Path]) -> dict[str, Any]:
    records = []
    for p in paths:
        stat = p.stat()
        records.append(
            {
                "path": str(p),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "sha256": sha256_file(p),
            }
        )

    dataset_hash = _sha256_bytes(
        "\n".join(f"{r['path']}::{r['sha256']}" for r in records).encode("utf-8")
    )

    return {
        "dataset_hash": dataset_hash,
        "documents": records,
        "count": len(records),
    }


def build_paragraph_manifest(samples: list[dict[str, Any]]) -> dict[str, Any]:
    payload = "\n".join(
        f"{s.get('sample_id')}::{s.get('document_id')}::{s.get('paragraph_id')}::{s.get('text', '')}"
        for s in samples
    )
    return {
        "dataset_hash": _sha256_bytes(payload.encode("utf-8")),
        "count": len(samples),
    }
