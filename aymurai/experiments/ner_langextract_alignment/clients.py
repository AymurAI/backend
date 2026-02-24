from __future__ import annotations

import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Iterable

import requests

DOC_EXTENSIONS = {".pdf", ".docx"}


def discover_documents(root: Path, extensions: Iterable[str]) -> list[Path]:
    exts = {e.lower() for e in extensions}
    return sorted(
        p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts
    )


def _request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    retries: int,
    backoff_s: float,
    timeout_s: float,
    **kwargs,
) -> requests.Response:
    attempt = 0
    while True:
        try:
            response = session.request(method, url, timeout=timeout_s, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt >= retries:
                raise
            attempt += 1
            time.sleep(backoff_s * attempt)


def call_extraction_api(
    session: requests.Session,
    *,
    base_url: str,
    path: str,
    file_path: Path,
    use_cache: bool,
    timeout_s: float,
    retries: int,
    retry_backoff_s: float,
) -> dict[str, Any]:
    """
    Robust extraction call that never raises and always returns a status payload.
    """
    payload: dict[str, Any] = {
        "path": str(file_path),
        "status": "failure",
        "status_code": None,
        "elapsed_ms": None,
        "detail": None,
    }

    if not file_path.exists():
        payload["detail"] = "File does not exist"
        return payload

    url = f"{base_url}{path}"
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    started = time.perf_counter()

    try:
        with file_path.open("rb") as fh:
            files = {"file": (file_path.name, fh, mime_type)}
            response = _request_with_retry(
                session,
                "POST",
                url,
                retries=retries,
                backoff_s=retry_backoff_s,
                timeout_s=timeout_s,
                params={"use_cache": str(use_cache).lower()},
                files=files,
            )
        payload["status_code"] = response.status_code
        payload["elapsed_ms"] = (time.perf_counter() - started) * 1000.0
    except requests.RequestException as exc:
        payload["elapsed_ms"] = (time.perf_counter() - started) * 1000.0
        payload["detail"] = f"Request failed: {exc}"
        return payload

    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text[:500]}

    if response.ok:
        payload["status"] = "success"
        payload["detail"] = {
            "document_id": body.get("document_id"),
            "document": body.get("document", []),
        }
    else:
        payload["detail"] = body

    return payload


def call_anonymizer_predict(
    session: requests.Session,
    *,
    base_url: str,
    path: str,
    text: str,
    use_cache: bool,
    timeout_s: float,
    retries: int,
    retry_backoff_s: float,
) -> tuple[dict[str, Any], float]:
    url = f"{base_url}{path}"
    start = time.perf_counter()
    response = _request_with_retry(
        session,
        "POST",
        url,
        retries=retries,
        backoff_s=retry_backoff_s,
        timeout_s=timeout_s,
        params={"use_cache": str(use_cache).lower()},
        json={"text": text},
    )

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return response.json(), elapsed_ms


def load_paragraphs_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records
