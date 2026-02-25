from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ComparisonStatus = Literal[
    "exact_match", "partial_match", "ner_only", "langextract_only", "mixed"
]


@dataclass(frozen=True)
class EntityKey:
    label: str
    start_char: int
    end_char: int
    text: str


@dataclass
class NormalizedEntity:
    label: str
    start_char: int
    end_char: int
    text: str
    source: Literal["ner", "langextract"]
    raw_label: str | None = None
    normalized_text: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def key(self) -> EntityKey:
        return EntityKey(
            label=self.label,
            start_char=self.start_char,
            end_char=self.end_char,
            text=self.text,
        )


@dataclass
class ComparisonResult:
    status: ComparisonStatus
    exact_match: list[NormalizedEntity]
    partial_match: list[NormalizedEntity]
    only_in_ner: list[NormalizedEntity]
    only_in_langextract: list[NormalizedEntity]


@dataclass
class SampleRecord:
    sample_id: str
    document_id: str
    paragraph_id: str
    source_path: str | None
    text: str
    ner_predictions: list[dict[str, Any]]
    langextract_predictions: list[dict[str, Any]]
    comparison: dict[str, Any]
    quality_flags: list[str]
    timestamps: dict[str, str]
    latency_ms: dict[str, float]


@dataclass
class LLMTrace:
    trace_id: str
    sample_id: str
    provider: str
    model: str
    prompt: str
    input_text: str
    raw_output: str | None
    parsed_output: dict[str, Any] | None
    duration_ms: float
    error: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
