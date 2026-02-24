from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from aymurai.experiments.ner_testset_evaluation.loaders import (
    spans_to_bio,
    token_offsets_from_text,
)
from aymurai.experiments.ner_testset_evaluation.types import (
    BackendPrediction,
    CanonicalSample,
    CanonicalSpan,
    EvaluationSummary,
    SampleScore,
)


def _safe_div(num: float, den: float) -> float:
    return float(num / den) if den else 0.0


def _f1(precision: float, recall: float) -> float:
    return _safe_div(2.0 * precision * recall, precision + recall)


def span_key(span: CanonicalSpan) -> tuple[str, int, int, str]:
    return (span.label, int(span.start), int(span.end), str(span.text))


def strip_bio_sequence(seq: list[str]) -> list[str]:
    cleaned: list[str] = []
    for label in seq:
        value = str(label or "").strip().upper()
        if not value or value == "O":
            cleaned.append("O")
            continue
        if "-" in value:
            prefix, rest = value.split("-", 1)
            if prefix in {"B", "I", "E", "S"}:
                cleaned.append(rest)
                continue
        cleaned.append(value)
    return cleaned


def compute_sample_strict_score(
    sample: CanonicalSample,
    prediction: BackendPrediction,
) -> SampleScore:
    gold_counter = Counter(span_key(span) for span in sample.gold_spans)
    pred_counter = Counter(span_key(span) for span in prediction.spans)

    labels = sorted(
        {
            key[0]
            for key in list(gold_counter.keys()) + list(pred_counter.keys())
            if key[0]
        }
    )

    tp = sum(min(gold_counter[key], pred_counter.get(key, 0)) for key in gold_counter)
    fp = sum(pred_counter.values()) - tp
    fn = sum(gold_counter.values()) - tp

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _f1(precision, recall)

    label_stats: dict[str, dict[str, float | int]] = {}
    for label in labels:
        gold_keys = {k for k in gold_counter if k[0] == label}
        pred_keys = {k for k in pred_counter if k[0] == label}

        label_tp = sum(
            min(gold_counter[key], pred_counter.get(key, 0)) for key in gold_keys
        )
        label_gold = sum(gold_counter[key] for key in gold_keys)
        label_pred = sum(pred_counter[key] for key in pred_keys)

        label_fp = label_pred - label_tp
        label_fn = label_gold - label_tp
        label_precision = _safe_div(label_tp, label_tp + label_fp)
        label_recall = _safe_div(label_tp, label_tp + label_fn)
        label_f1 = _f1(label_precision, label_recall)

        label_stats[label] = {
            "tp": int(label_tp),
            "fp": int(label_fp),
            "fn": int(label_fn),
            "support": int(label_gold),
            "precision": float(label_precision),
            "recall": float(label_recall),
            "f1": float(label_f1),
        }

    return SampleScore(
        sample_id=sample.sample_id,
        tp=int(tp),
        fp=int(fp),
        fn=int(fn),
        precision=float(precision),
        recall=float(recall),
        f1=float(f1),
        perfect_span_set=bool(fp == 0 and fn == 0),
        label_stats=label_stats,
    )


def _sample_token_sequences(
    sample: CanonicalSample,
    prediction: BackendPrediction,
) -> tuple[list[str], list[str], float]:
    tokens = sample.tokens if sample.tokens else str(sample.text or "").split()
    offsets = token_offsets_from_text(sample.text, tokens)

    if sample.gold_bio is not None and len(sample.gold_bio) == len(tokens):
        gold_bio = [str(x) for x in sample.gold_bio]
    else:
        gold_bio = spans_to_bio(spans=sample.gold_spans, token_offsets=offsets)

    pred_bio = spans_to_bio(spans=prediction.spans, token_offsets=offsets)
    token_accuracy = _safe_div(
        sum(1 for g, p in zip(gold_bio, pred_bio) if g == p),
        len(gold_bio),
    )
    return gold_bio, pred_bio, token_accuracy


def compute_relaxed_metrics(
    sequence_pairs: list[tuple[list[str], list[str]]],
) -> tuple[
    dict[str, dict[str, float | int]],
    dict[str, float],
    float,
    list[dict[str, Any]],
]:
    gold_flat: list[str] = []
    pred_flat: list[str] = []

    for gold_seq, pred_seq in sequence_pairs:
        stripped_gold = strip_bio_sequence(gold_seq)
        stripped_pred = strip_bio_sequence(pred_seq)
        gold_flat.extend(stripped_gold)
        pred_flat.extend(stripped_pred)

    labels = sorted({lab for lab in gold_flat + pred_flat if lab != "O"})

    per_label: dict[str, dict[str, float | int]] = {}
    tp_total = fp_total = fn_total = 0

    for label in labels:
        tp = sum(1 for g, p in zip(gold_flat, pred_flat) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold_flat, pred_flat) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold_flat, pred_flat) if g == label and p != label)
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _f1(precision, recall)
        support = sum(1 for g in gold_flat if g == label)

        per_label[label] = {
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "support": int(support),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }
        tp_total += tp
        fp_total += fp
        fn_total += fn

    micro_precision = _safe_div(tp_total, tp_total + fp_total)
    micro_recall = _safe_div(tp_total, tp_total + fn_total)
    micro_f1 = _f1(micro_precision, micro_recall)
    accuracy = _safe_div(
        sum(1 for g, p in zip(gold_flat, pred_flat) if g == p),
        len(gold_flat),
    )

    confusion: dict[tuple[str, str], int] = defaultdict(int)
    for g, p in zip(gold_flat, pred_flat):
        confusion[(g, p)] += 1

    confusion_rows = [
        {"gold_label": g, "pred_label": p, "count": int(count)}
        for (g, p), count in sorted(
            confusion.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ]

    return (
        per_label,
        {
            "precision": float(micro_precision),
            "recall": float(micro_recall),
            "f1": float(micro_f1),
        },
        float(accuracy),
        confusion_rows,
    )


def _aggregate_strict_label_metrics(
    sample_scores: list[SampleScore],
) -> dict[str, dict[str, float | int]]:
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0, "support": 0}
    )

    for sample_score in sample_scores:
        for label, stats in sample_score.label_stats.items():
            totals[label]["tp"] += int(stats.get("tp", 0))
            totals[label]["fp"] += int(stats.get("fp", 0))
            totals[label]["fn"] += int(stats.get("fn", 0))
            totals[label]["support"] += int(stats.get("support", 0))

    out: dict[str, dict[str, float | int]] = {}
    for label, stats in sorted(totals.items()):
        precision = _safe_div(stats["tp"], stats["tp"] + stats["fp"])
        recall = _safe_div(stats["tp"], stats["tp"] + stats["fn"])
        out[label] = {
            "tp": int(stats["tp"]),
            "fp": int(stats["fp"]),
            "fn": int(stats["fn"]),
            "support": int(stats["support"]),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(_f1(precision, recall)),
        }
    return out


def evaluate_predictions(
    samples: list[CanonicalSample],
    predictions: list[BackendPrediction],
    *,
    include_token_relaxed: bool,
) -> tuple[list[SampleScore], EvaluationSummary, list[dict[str, Any]]]:
    pred_by_id = {prediction.sample_id: prediction for prediction in predictions}

    sample_scores: list[SampleScore] = []
    strict_tp = strict_fp = strict_fn = 0

    sequence_pairs: list[tuple[list[str], list[str]]] = []

    for sample in samples:
        prediction = pred_by_id.get(
            sample.sample_id,
            BackendPrediction(
                sample_id=sample.sample_id, backend_mode="ner_api", spans=[]
            ),
        )

        sample_score = compute_sample_strict_score(sample, prediction)
        strict_tp += sample_score.tp
        strict_fp += sample_score.fp
        strict_fn += sample_score.fn

        if include_token_relaxed:
            gold_bio, pred_bio, token_accuracy = _sample_token_sequences(
                sample, prediction
            )
            sample_score.token_relaxed_accuracy = token_accuracy
            sequence_pairs.append((gold_bio, pred_bio))

        sample_scores.append(sample_score)

    strict_precision = _safe_div(strict_tp, strict_tp + strict_fp)
    strict_recall = _safe_div(strict_tp, strict_tp + strict_fn)
    strict_f1 = _f1(strict_precision, strict_recall)

    strict_label_metrics = _aggregate_strict_label_metrics(sample_scores)
    strict_macro_precision = (
        mean(float(stats["precision"]) for stats in strict_label_metrics.values())
        if strict_label_metrics
        else 0.0
    )
    strict_macro_recall = (
        mean(float(stats["recall"]) for stats in strict_label_metrics.values())
        if strict_label_metrics
        else 0.0
    )
    strict_macro_f1 = (
        mean(float(stats["f1"]) for stats in strict_label_metrics.values())
        if strict_label_metrics
        else 0.0
    )

    perfect_count = sum(1 for score in sample_scores if score.perfect_span_set)
    perfect_rate = _safe_div(perfect_count, len(sample_scores))

    relaxed_label_metrics: dict[str, dict[str, float | int]] = {}
    relaxed_micro = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    relaxed_accuracy = 0.0
    confusion_rows: list[dict[str, Any]] = []

    if include_token_relaxed:
        (
            relaxed_label_metrics,
            relaxed_micro,
            relaxed_accuracy,
            confusion_rows,
        ) = compute_relaxed_metrics(sequence_pairs)

    metrics = {
        "samples_count": float(len(sample_scores)),
        "strict_tp": float(strict_tp),
        "strict_fp": float(strict_fp),
        "strict_fn": float(strict_fn),
        "strict_precision": float(strict_precision),
        "strict_recall": float(strict_recall),
        "strict_f1": float(strict_f1),
        "strict_macro_precision": float(strict_macro_precision),
        "strict_macro_recall": float(strict_macro_recall),
        "strict_macro_f1": float(strict_macro_f1),
        "perfect_span_set_count": float(perfect_count),
        "perfect_span_set_rate": float(perfect_rate),
    }

    if include_token_relaxed:
        metrics.update(
            {
                "token_relaxed_micro_precision": float(relaxed_micro["precision"]),
                "token_relaxed_micro_recall": float(relaxed_micro["recall"]),
                "token_relaxed_micro_f1": float(relaxed_micro["f1"]),
                "token_relaxed_accuracy": float(relaxed_accuracy),
            }
        )

    summary = EvaluationSummary(
        sample_count=len(sample_scores),
        metrics=metrics,
        strict_label_metrics=strict_label_metrics,
        token_relaxed_label_metrics=relaxed_label_metrics,
        token_relaxed_micro=relaxed_micro,
    )

    return sample_scores, summary, confusion_rows
