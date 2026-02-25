from __future__ import annotations

import string
from dataclasses import asdict
from typing import Any

from unidecode import unidecode

from aymurai.experiments.ner_langextract_alignment.types import NormalizedEntity


PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def normalize_label(label: str) -> str:
    return str(label).strip().upper()


def normalize_text(
    text: str,
    *,
    normalize_case: bool,
    normalize_accents: bool,
    normalize_punctuation: bool,
) -> str:
    value = text.strip()
    if normalize_case:
        value = value.lower()
    if normalize_accents:
        value = unidecode(value)
    if normalize_punctuation:
        value = value.translate(PUNCT_TABLE)
    return " ".join(value.split())


def serialize_entity(entity: NormalizedEntity) -> dict[str, Any]:
    payload = asdict(entity)
    payload["key"] = {
        "label": entity.label,
        "start_char": entity.start_char,
        "end_char": entity.end_char,
        "text": entity.text,
    }
    return payload


def parse_ner_predictions(
    *,
    text: str,
    labels: list[dict[str, Any]],
    normalize_case: bool,
    normalize_accents: bool,
    normalize_punctuation: bool,
) -> tuple[list[NormalizedEntity], list[str]]:
    entities: list[NormalizedEntity] = []
    flags: list[str] = []

    for idx, label in enumerate(labels or []):
        attrs = label.get("attrs") or {}
        raw_label = attrs.get("aymurai_label") or label.get("label")
        alt_text = attrs.get("aymurai_alt_text")

        if not raw_label:
            flags.append(f"ner_missing_label:{idx}")
            continue

        start = label.get("start_char")
        end = label.get("end_char")
        if (
            start is None
            or end is None
            or not isinstance(start, int)
            or not isinstance(end, int)
        ):
            flags.append(f"ner_missing_span:{idx}")
            continue

        if start < 0 or end <= start or end > len(text):
            flags.append(f"ner_invalid_span:{idx}")
            continue

        exact_text = alt_text or text[start:end]
        entities.append(
            NormalizedEntity(
                label=normalize_label(raw_label),
                start_char=start,
                end_char=end,
                text=exact_text,
                source="ner",
                raw_label=str(raw_label),
                normalized_text=normalize_text(
                    exact_text,
                    normalize_case=normalize_case,
                    normalize_accents=normalize_accents,
                    normalize_punctuation=normalize_punctuation,
                ),
                extra={
                    "attrs": attrs,
                    "original_text": label.get("text"),
                    "alt_text": alt_text,
                },
            )
        )

    return entities, flags


def parse_langextract_predictions(
    *,
    text: str,
    extractions: list[dict[str, Any]],
    label_mapping: dict[str, str],
    normalize_case: bool,
    normalize_accents: bool,
    normalize_punctuation: bool,
) -> tuple[list[NormalizedEntity], list[str]]:
    entities: list[NormalizedEntity] = []
    flags: list[str] = []

    for idx, ext in enumerate(extractions or []):
        raw_class = str(ext.get("extraction_class") or "").strip()
        if not raw_class:
            flags.append(f"langextract_missing_class:{idx}")
            continue

        mapped = label_mapping.get(normalize_label(raw_class))
        if not mapped:
            flags.append(f"langextract_unmapped_class:{raw_class}")
            continue

        interval = ext.get("char_interval") or {}
        start = interval.get("start_pos")
        end = interval.get("end_pos")

        if (
            start is None
            or end is None
            or not isinstance(start, int)
            or not isinstance(end, int)
        ):
            flags.append(f"langextract_missing_span:{idx}")
            continue

        if start < 0 or end <= start or end > len(text):
            flags.append(f"langextract_invalid_span:{idx}")
            continue

        exact_text = text[start:end]
        entities.append(
            NormalizedEntity(
                label=normalize_label(mapped),
                start_char=start,
                end_char=end,
                text=exact_text,
                source="langextract",
                raw_label=raw_class,
                normalized_text=normalize_text(
                    exact_text,
                    normalize_case=normalize_case,
                    normalize_accents=normalize_accents,
                    normalize_punctuation=normalize_punctuation,
                ),
                extra={
                    "raw_class": raw_class,
                    "raw_text": ext.get("extraction_text"),
                    "alignment_status": ext.get("alignment_status"),
                },
            )
        )

    return entities, flags
