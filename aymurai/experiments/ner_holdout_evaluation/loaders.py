from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from aymurai.database.utils import text_to_uuid
from aymurai.experiments.ner_holdout_evaluation.config import NERHoldoutEvaluationConfig
from aymurai.experiments.ner_holdout_evaluation.types import (
    CanonicalSample,
    CanonicalSpan,
)
from aymurai.transforms.anonymization_postprocess.core import clean_entity_boundaries


def normalize_bio_label(tag: str | None) -> tuple[str, str | None]:
    value = str(tag or "").strip()
    if not value or value.upper() == "O":
        return "O", None

    upper = value.upper()
    if "-" in upper:
        prefix, label = upper.split("-", 1)
        if prefix in {"B", "I", "E", "S"}:
            return prefix, label
    return "B", upper


def token_offsets_from_text(text: str, tokens: list[str]) -> list[tuple[int, int]]:
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for token in tokens:
        if not token:
            offsets.append((cursor, cursor))
            continue
        start = text.find(token, cursor)
        if start < 0:
            start = cursor
        end = start + len(token)
        offsets.append((start, end))
        cursor = end
    return offsets


def whitespace_tokenize_with_offsets(
    text: str,
) -> tuple[list[str], list[tuple[int, int]]]:
    tokens = str(text or "").split()
    offsets = token_offsets_from_text(text, tokens)
    return tokens, offsets


def spans_to_bio(
    *,
    spans: list[CanonicalSpan],
    token_offsets: list[tuple[int, int]],
    default_label: str = "O",
) -> list[str]:
    labels = [default_label] * len(token_offsets)
    for span in spans:
        first = True
        for idx, (tok_start, tok_end) in enumerate(token_offsets):
            if span.end <= tok_start or span.start >= tok_end:
                continue
            prefix = "B-" if first else "I-"
            labels[idx] = f"{prefix}{span.label}"
            first = False
    return labels


def bio_to_spans(
    *,
    text: str,
    tokens: list[str],
    bio_labels: list[str],
    source: str = "gold",
) -> list[CanonicalSpan]:
    offsets = token_offsets_from_text(text, tokens)
    spans: list[CanonicalSpan] = []

    current_label: str | None = None
    current_start: int | None = None
    current_end: int | None = None

    def _build_span(
        *,
        label: str,
        start: int,
        end: int,
        source: str,
    ) -> CanonicalSpan:
        span_text = text[start:end]
        cleaned = clean_entity_boundaries(
            span_text,
            start_char=start,
            end_char=end,
        )
        return CanonicalSpan(
            label=label,
            start=start,
            end=end,
            text=span_text,
            raw_label=label,
            source=source,
            normalized_text=cleaned["text"] if cleaned is not None else span_text,
            alt_start_char=cleaned["start_char"] if cleaned is not None else start,
            alt_end_char=cleaned["end_char"] if cleaned is not None else end,
        )

    def close_current() -> None:
        nonlocal current_label, current_start, current_end
        if current_label is None or current_start is None or current_end is None:
            current_label = None
            current_start = None
            current_end = None
            return
        spans.append(
            _build_span(
                label=current_label,
                start=current_start,
                end=current_end,
                source=source,
            )
        )
        current_label = None
        current_start = None
        current_end = None

    for idx, tag in enumerate(bio_labels):
        if idx >= len(offsets):
            break
        token_start, token_end = offsets[idx]
        prefix, label = normalize_bio_label(tag)

        if prefix == "O" or label is None:
            close_current()
            continue

        if prefix == "S":
            close_current()
            spans.append(
                _build_span(
                    label=label,
                    start=token_start,
                    end=token_end,
                    source=source,
                )
            )
            continue

        if prefix == "B":
            close_current()
            current_label = label
            current_start = token_start
            current_end = token_end
            continue

        if prefix == "I":
            if current_label is None or current_start is None or current_label != label:
                current_label = label
                current_start = token_start
                current_end = token_end
            else:
                current_end = token_end
            continue

        if prefix == "E":
            if current_label is None or current_start is None or current_label != label:
                spans.append(
                    _build_span(
                        label=label,
                        start=token_start,
                        end=token_end,
                        source=source,
                    )
                )
            else:
                current_end = token_end
                close_current()

    close_current()
    return spans


def _load_json_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return payload["data"]
        return [payload]
    raise ValueError(f"Unsupported JSON payload at {path}")


def _ensure_unique_sample_ids(samples: list[CanonicalSample]) -> list[CanonicalSample]:
    seen: Counter[str] = Counter()
    for sample in samples:
        seen[sample.sample_id] += 1
        if seen[sample.sample_id] > 1:
            sample.sample_id = f"{sample.sample_id}-{seen[sample.sample_id]-1}"
    return samples


def load_conll_bio(path: Path) -> list[CanonicalSample]:
    rows = path.read_text(encoding="utf-8").splitlines()
    tokens: list[str] = []
    labels: list[str] = []
    samples: list[CanonicalSample] = []

    def flush() -> None:
        nonlocal tokens, labels
        if not tokens:
            return
        text = " ".join(tokens).strip()
        spans = bio_to_spans(text=text, tokens=tokens, bio_labels=labels, source="gold")
        sample_id = text_to_uuid(text).hex
        samples.append(
            CanonicalSample(
                sample_id=sample_id,
                text=text,
                tokens=list(tokens),
                gold_spans=spans,
                gold_bio=list(labels),
                metadata={"format": "conll_bio"},
            )
        )
        tokens = []
        labels = []

    for raw_line in rows:
        line = raw_line.rstrip("\n")
        if not line.strip():
            flush()
            continue
        try:
            token, label = line.rsplit(" ", 1)
        except ValueError:
            token, label = line, "O"
        tokens.append(str(token))
        labels.append(str(label).strip() or "O")

    flush()
    return _ensure_unique_sample_ids(samples)


def load_hf_token_classification(
    path: Path,
    *,
    text_field: str,
    tokens_field: str,
    tags_field: str,
    sample_id_field: str,
    id2label: dict[str, str] | None,
) -> list[CanonicalSample]:
    records = _load_json_records(path)
    samples: list[CanonicalSample] = []

    for index, row in enumerate(records):
        raw_tokens = row.get(tokens_field, [])
        raw_tags = row.get(tags_field, [])
        if not isinstance(raw_tokens, list) or not isinstance(raw_tags, list):
            continue
        if len(raw_tokens) != len(raw_tags):
            continue

        row_id2label = (
            row.get("id2label") if isinstance(row.get("id2label"), dict) else {}
        )
        merged_id2label = dict(id2label or {})
        merged_id2label.update({str(k): str(v) for k, v in row_id2label.items()})

        tokens = [str(t) for t in raw_tokens]
        bio_labels: list[str] = []
        for tag in raw_tags:
            if isinstance(tag, int):
                mapped = merged_id2label.get(str(tag), str(tag))
                bio_labels.append(str(mapped))
            else:
                bio_labels.append(str(tag))

        text_value = row.get(text_field)
        text = (
            str(text_value)
            if isinstance(text_value, str) and text_value
            else " ".join(tokens)
        )
        sample_id = str(
            row.get(sample_id_field) or text_to_uuid(text).hex or f"sample-{index}"
        )

        spans = bio_to_spans(
            text=text, tokens=tokens, bio_labels=bio_labels, source="gold"
        )
        samples.append(
            CanonicalSample(
                sample_id=sample_id,
                text=text,
                tokens=tokens,
                gold_spans=spans,
                gold_bio=bio_labels,
                metadata={"format": "hf_token_classification", "index": index},
            )
        )

    return _ensure_unique_sample_ids(samples)


def _parse_raw_span(
    *,
    span_row: dict[str, Any],
    text: str,
    default_label_field: str,
    default_start_field: str,
    default_end_field: str,
) -> CanonicalSpan | None:
    label = (
        span_row.get(default_label_field)
        or span_row.get("aymurai_label")
        or span_row.get("extraction_class")
    )
    start = span_row.get(default_start_field)
    end = span_row.get(default_end_field)

    if start is None and isinstance(span_row.get("char_interval"), dict):
        start = span_row["char_interval"].get("start_pos")
    if end is None and isinstance(span_row.get("char_interval"), dict):
        end = span_row["char_interval"].get("end_pos")
    if start is None:
        start = span_row.get("start_char")
    if end is None:
        end = span_row.get("end_char")

    if label is None or not isinstance(start, int) or not isinstance(end, int):
        return None
    if start < 0 or end <= start or end > len(text):
        return None

    span_text = str(
        span_row.get("text") or span_row.get("extraction_text") or text[start:end]
    )
    cleaned = clean_entity_boundaries(
        span_text,
        start_char=int(start),
        end_char=int(end),
    )
    return CanonicalSpan(
        label=str(label).strip().upper(),
        start=int(start),
        end=int(end),
        text=span_text,
        raw_label=str(label),
        source="gold",
        normalized_text=cleaned["text"] if cleaned is not None else span_text,
        alt_start_char=cleaned["start_char"] if cleaned is not None else int(start),
        alt_end_char=cleaned["end_char"] if cleaned is not None else int(end),
        extra={"raw": span_row},
    )


def load_span_jsonl(
    path: Path,
    *,
    sample_id_field: str,
    text_field: str,
    tokens_field: str,
    spans_field: str,
    label_field: str,
    start_field: str,
    end_field: str,
) -> list[CanonicalSample]:
    records = _load_json_records(path)
    samples: list[CanonicalSample] = []

    for index, row in enumerate(records):
        text = str(row.get(text_field) or "")
        if not text:
            continue

        raw_tokens = row.get(tokens_field)
        tokens = (
            [str(t) for t in raw_tokens]
            if isinstance(raw_tokens, list)
            else text.split()
        )

        raw_spans = row.get(spans_field, [])
        spans: list[CanonicalSpan] = []
        if isinstance(raw_spans, list):
            for span_row in raw_spans:
                if not isinstance(span_row, dict):
                    continue
                parsed = _parse_raw_span(
                    span_row=span_row,
                    text=text,
                    default_label_field=label_field,
                    default_start_field=start_field,
                    default_end_field=end_field,
                )
                if parsed is not None:
                    spans.append(parsed)

        gold_bio = (
            row.get("gold_bio") if isinstance(row.get("gold_bio"), list) else None
        )
        if gold_bio is None and tokens:
            offsets = token_offsets_from_text(text, tokens)
            gold_bio = spans_to_bio(spans=spans, token_offsets=offsets)

        sample_id = str(
            row.get(sample_id_field) or text_to_uuid(text).hex or f"sample-{index}"
        )
        samples.append(
            CanonicalSample(
                sample_id=sample_id,
                text=text,
                tokens=tokens,
                gold_spans=spans,
                gold_bio=[str(x) for x in gold_bio] if gold_bio is not None else None,
                metadata={"format": "span_jsonl", "index": index},
            )
        )

    return _ensure_unique_sample_ids(samples)


def deduplicate_samples_by_text(
    samples: list[CanonicalSample],
) -> list[CanonicalSample]:
    seen: set[str] = set()
    unique: list[CanonicalSample] = []
    for sample in samples:
        key = " ".join(sample.text.split())
        if key in seen:
            continue
        seen.add(key)
        unique.append(sample)
    return unique


def load_samples(config: NERHoldoutEvaluationConfig) -> list[CanonicalSample]:
    path = Path(config.data.input_path)

    if config.data.format == "conll_bio":
        samples = load_conll_bio(path)
    elif config.data.format == "hf_token_classification":
        samples = load_hf_token_classification(
            path,
            text_field=config.data.text_field,
            tokens_field=config.data.tokens_field,
            tags_field=config.data.tags_field,
            sample_id_field=config.data.sample_id_field,
            id2label=config.data.id2label,
        )
    elif config.data.format == "span_jsonl":
        samples = load_span_jsonl(
            path,
            sample_id_field=config.data.sample_id_field,
            text_field=config.data.text_field,
            tokens_field=config.data.tokens_field,
            spans_field=config.data.spans_field,
            label_field=config.data.label_field,
            start_field=config.data.start_field,
            end_field=config.data.end_field,
        )
    else:
        raise ValueError(f"Unsupported data.format={config.data.format}")

    if config.data.deduplicate_by_text:
        samples = deduplicate_samples_by_text(samples)

    if config.data.max_samples is not None:
        samples = samples[: config.data.max_samples]

    return samples
