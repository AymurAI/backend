from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatasetInfo:
    dataset_hash: str
    dataset_count: int
    dataset_bytes_total: int
    manifest: dict | None = None


def build_metadata_manifest(root_dir: Path) -> DatasetInfo:
    files = []
    total_bytes = 0

    for path in sorted(root_dir.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        rel_path = path.relative_to(root_dir).as_posix()
        files.append(
            {
                "path": rel_path,
                "size_bytes": stat.st_size,
                "mtime": int(stat.st_mtime),
            }
        )
        total_bytes += stat.st_size

    manifest = {"files": files, "summary": {"count": len(files), "bytes": total_bytes}}
    manifest_bytes = json.dumps(files, sort_keys=True).encode("utf-8")
    dataset_hash = hashlib.sha256(manifest_bytes).hexdigest()

    return DatasetInfo(
        dataset_hash=dataset_hash,
        dataset_count=len(files),
        dataset_bytes_total=total_bytes,
        manifest=manifest,
    )
