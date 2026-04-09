from __future__ import annotations

from collections import Counter
from typing import Any

from flair.data import Sentence

from aymurai.experiments.ner_flair_finetuning.types import (
    BackendPrediction,
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


def _span_from_entity(entity: Any, sentence_text: str, source: str) -> CanonicalSpan:
    label = entity.get_label("ner").value
    text = str(entity.text)
    start = int(entity.start_position)
    end = int(entity.end_position)

    cleaned = clean_entity_boundaries(
        sentence_text,
        start_char=start,
        end_char=end,
    )

    return CanonicalSpan(
        label=label,
        start=start,
        end=end,
        text=text,
        source=source,
        raw_label=label,
        normalized_text=cleaned["text"] if cleaned else text,
        alt_start_char=cleaned["start_char"] if cleaned else start,
        alt_end_char=cleaned["end_char"] if cleaned else end,
    )


def sentence_to_canonical_sample(sentence: Sentence, sample_id: str) -> CanonicalSample:
    spans = [
        _span_from_entity(entity, sentence.text, "gold")
        for entity in sentence.get_spans("ner")
    ]
    return CanonicalSample(
        sample_id=sample_id,
        text=sentence.to_plain_string(),
        tokens=[t.text for t in sentence.tokens],
        gold_spans=spans,
    )


def flair_to_prediction(
    sentence: Sentence,
    sample_id: str,
    *,
    backend_mode: str,
) -> BackendPrediction:
    spans = [
        _span_from_entity(entity, sentence.text, "flair_local")
        for entity in sentence.get_spans("ner")
    ]
    return BackendPrediction(
        sample_id=sample_id, backend_mode=backend_mode, spans=spans
    )


def _multiset_diff(
    a: list[CanonicalSpan], b: list[CanonicalSpan]
) -> list[dict[str, Any]]:
    b_counter = Counter(span.key() for span in b)
    rows: list[dict[str, Any]] = []
    for span in a:
        key = span.key()
        if b_counter.get(key, 0) > 0:
            b_counter[key] -= 1
            continue
        rows.append(
            {
                "label": span.label,
                "start": span.start,
                "end": span.end,
                "text": span.text,
                "alt_start_char": span.alt_start_char,
                "alt_end_char": span.alt_end_char,
            }
        )
    return rows


def build_span_comparison_row(
    gold_sample: CanonicalSample,
    prediction: BackendPrediction,
    *,
    split: str,
    epoch: int | None = None,
) -> dict[str, Any]:
    gold_spans = [
        {
            "label": span.label,
            "start": span.start,
            "end": span.end,
            "text": span.text,
            "alt_start_char": span.alt_start_char,
            "alt_end_char": span.alt_end_char,
        }
        for span in gold_sample.gold_spans
    ]
    pred_spans = [
        {
            "label": span.label,
            "start": span.start,
            "end": span.end,
            "text": span.text,
            "alt_start_char": span.alt_start_char,
            "alt_end_char": span.alt_end_char,
        }
        for span in prediction.spans
    ]

    false_negatives = _multiset_diff(gold_sample.gold_spans, prediction.spans)
    false_positives = _multiset_diff(prediction.spans, gold_sample.gold_spans)

    return {
        "sample_id": gold_sample.sample_id,
        "split": split,
        "epoch": epoch,
        "text": gold_sample.text,
        "gold_spans": gold_spans,
        "predicted_spans": pred_spans,
        "false_negatives": false_negatives,
        "false_positives": false_positives,
        "perfect_span_set": len(false_negatives) == 0 and len(false_positives) == 0,
    }
