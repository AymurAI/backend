from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


BackendMode = Literal["ner_api", "langextract"]


@dataclass
class CanonicalSpan:
    label: str
    start: int
    end: int
    text: str
    raw_label: str | None = None
    source: str = "gold"
    normalized_text: str | None = None
    alt_start_char: int | None = None
    alt_end_char: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def key(self) -> tuple[str, int, int, str]:
        return (
            self.label,
            self.alt_start_char if self.alt_start_char is not None else self.start,
            self.alt_end_char if self.alt_end_char is not None else self.end,
            self.normalized_text or self.text,
        )


@dataclass
class CanonicalSample:
    sample_id: str
    text: str
    tokens: list[str] = field(default_factory=list)
    gold_spans: list[CanonicalSpan] = field(default_factory=list)
    gold_bio: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackendPrediction:
    sample_id: str
    backend_mode: BackendMode
    spans: list[CanonicalSpan] = field(default_factory=list)
    latency_ms: float = 0.0
    error: str | None = None
    raw_payload: dict[str, Any] | None = None
    quality_flags: list[str] = field(default_factory=list)
    trace_ids: list[str] = field(default_factory=list)


@dataclass
class SampleScore:
    sample_id: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    perfect_span_set: bool
    entity_match_rate: float | None = None
    label_stats: dict[str, dict[str, float | int]] = field(default_factory=dict)
    token_relaxed_accuracy: float | None = None


@dataclass
class EvaluationSummary:
    sample_count: int
    metrics: dict[str, float]
    strict_label_metrics: dict[str, dict[str, float | int]]
    token_relaxed_label_metrics: dict[str, dict[str, float | int]]
    token_relaxed_micro: dict[str, float]


@dataclass
class FeedbackRecord:
    name: str
    value: Any
    sample_id: str
    perfect_span_set: bool | None = None
    rationale: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def span_to_dict(span: CanonicalSpan) -> dict[str, Any]:
    return asdict(span)


def sample_to_dict(sample: CanonicalSample) -> dict[str, Any]:
    payload = asdict(sample)
    payload["gold_spans"] = [span_to_dict(s) for s in sample.gold_spans]
    return payload


def prediction_to_dict(prediction: BackendPrediction) -> dict[str, Any]:
    payload = asdict(prediction)
    payload["spans"] = [span_to_dict(s) for s in prediction.spans]
    return payload


def score_to_dict(score: SampleScore) -> dict[str, Any]:
    return asdict(score)


def feedback_to_dict(feedback: FeedbackRecord) -> dict[str, Any]:
    return asdict(feedback)
