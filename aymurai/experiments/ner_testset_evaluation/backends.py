from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from aymurai.experiments.ner_langextract_alignment.clients import (
    call_anonymizer_predict,
)
from aymurai.experiments.ner_langextract_alignment.langextract_runner import (
    build_tracing_model,
    load_examples_from_yaml,
    run_langextract,
)
from aymurai.experiments.ner_langextract_alignment.normalize import (
    parse_langextract_predictions,
    parse_ner_predictions,
)
from aymurai.experiments.ner_langextract_alignment.types import LLMTrace
from aymurai.experiments.ner_testset_evaluation.config import NERTestsetEvaluationConfig
from aymurai.experiments.ner_testset_evaluation.types import (
    BackendPrediction,
    CanonicalSample,
    CanonicalSpan,
)
from aymurai.utils.yaml_data import load_yaml


def _load_label_mapping(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    payload = load_yaml(path)
    mapping = payload.get("labels", payload) if isinstance(payload, dict) else {}
    return {str(k).strip().upper(): str(v).strip().upper() for k, v in mapping.items()}


def _map_label(label: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return label
    return mapping.get(str(label).strip().upper(), str(label).strip().upper())


def _entities_to_spans(
    entities: list[Any],
    *,
    source: str,
    label_mapping: dict[str, str] | None = None,
) -> list[CanonicalSpan]:
    mapping = label_mapping or {}
    spans: list[CanonicalSpan] = []
    for entity in entities:
        mapped_label = _map_label(entity.label, mapping)
        spans.append(
            CanonicalSpan(
                label=mapped_label,
                start=int(entity.start_char),
                end=int(entity.end_char),
                text=str(entity.text),
                raw_label=str(entity.raw_label)
                if entity.raw_label is not None
                else str(entity.label),
                source=source,
                normalized_text=entity.normalized_text,
                extra=dict(entity.extra or {}),
            )
        )
    return spans


def _run_ner_api_backend(
    samples: list[CanonicalSample],
    config: NERTestsetEvaluationConfig,
    *,
    label_mapping: dict[str, str],
) -> tuple[list[BackendPrediction], list[LLMTrace]]:
    session = requests.Session()
    predictions: list[BackendPrediction] = []

    for sample in samples:
        text = str(sample.text or "")
        if not text.strip():
            predictions.append(
                BackendPrediction(
                    sample_id=sample.sample_id,
                    backend_mode="ner_api",
                    spans=[],
                    latency_ms=0.0,
                    error="empty_or_invalid_input",
                    quality_flags=["empty_or_invalid_input"],
                    raw_payload={"labels": []},
                )
            )
            continue

        try:
            payload, latency_ms = call_anonymizer_predict(
                session,
                base_url=config.api.base_url,
                path=config.api.anonymizer_predict_path,
                text=text,
                use_cache=config.api.use_cache,
                timeout_s=config.api.timeout_s,
                retries=config.api.retries,
                retry_backoff_s=config.api.retry_backoff_s,
            )
            entities, flags = parse_ner_predictions(
                text=text,
                labels=payload.get("labels", []),
                normalize_case=config.comparison.normalize_case,
                normalize_accents=config.comparison.normalize_accents,
                normalize_punctuation=config.comparison.normalize_punctuation,
            )
            spans = _entities_to_spans(
                entities,
                source="ner_api",
                label_mapping=label_mapping,
            )
            predictions.append(
                BackendPrediction(
                    sample_id=sample.sample_id,
                    backend_mode="ner_api",
                    spans=spans,
                    latency_ms=float(latency_ms),
                    error=None,
                    quality_flags=list(flags),
                    raw_payload=payload,
                    trace_ids=[],
                )
            )
        except Exception as exc:
            predictions.append(
                BackendPrediction(
                    sample_id=sample.sample_id,
                    backend_mode="ner_api",
                    spans=[],
                    latency_ms=0.0,
                    error=str(exc),
                    quality_flags=["ner_api_inference_error"],
                    raw_payload={"labels": []},
                    trace_ids=[],
                )
            )

    return predictions, []


def _run_langextract_backend(
    samples: list[CanonicalSample],
    config: NERTestsetEvaluationConfig,
    *,
    label_mapping: dict[str, str],
) -> tuple[list[BackendPrediction], list[LLMTrace]]:
    if config.langextract is None:
        raise ValueError("langextract config is required when backend.mode=langextract")

    examples = load_examples_from_yaml(config.langextract.examples_yaml_path)
    if not examples:
        raise ValueError(
            f"No examples loaded from {config.langextract.examples_yaml_path}"
        )

    model = build_tracing_model(config.langextract)
    predictions: list[BackendPrediction] = []
    traces: list[LLMTrace] = []

    for sample in samples:
        text = str(sample.text or "")
        try:
            payload, sample_traces, latency_ms = run_langextract(
                sample_id=sample.sample_id,
                text=text,
                config=config.langextract,
                examples=examples,
                model=model,
            )
            entities, flags = parse_langextract_predictions(
                text=text,
                extractions=payload.get("extractions", []),
                label_mapping=label_mapping,
                normalize_case=config.comparison.normalize_case,
                normalize_accents=config.comparison.normalize_accents,
                normalize_punctuation=config.comparison.normalize_punctuation,
            )
            if payload.get("error"):
                flags.append("langextract_inference_error")

            spans = _entities_to_spans(entities, source="langextract")
            trace_ids = [t.trace_id for t in sample_traces]
            traces.extend(sample_traces)
            predictions.append(
                BackendPrediction(
                    sample_id=sample.sample_id,
                    backend_mode="langextract",
                    spans=spans,
                    latency_ms=float(latency_ms),
                    error=str(payload.get("error")) if payload.get("error") else None,
                    quality_flags=sorted(set(flags)),
                    raw_payload=payload,
                    trace_ids=trace_ids,
                )
            )
        except Exception as exc:
            predictions.append(
                BackendPrediction(
                    sample_id=sample.sample_id,
                    backend_mode="langextract",
                    spans=[],
                    latency_ms=0.0,
                    error=str(exc),
                    quality_flags=["langextract_inference_error"],
                    raw_payload={"extractions": []},
                    trace_ids=[],
                )
            )

    return predictions, traces


def run_backend_inference(
    samples: list[CanonicalSample],
    config: NERTestsetEvaluationConfig,
) -> tuple[list[BackendPrediction], list[LLMTrace], dict[str, str]]:
    label_mapping = _load_label_mapping(config.mapping.labels_yaml_path)

    if config.backend.mode == "ner_api":
        predictions, traces = _run_ner_api_backend(
            samples,
            config,
            label_mapping=label_mapping,
        )
    elif config.backend.mode == "langextract":
        predictions, traces = _run_langextract_backend(
            samples,
            config,
            label_mapping=label_mapping,
        )
    else:
        raise ValueError(f"Unsupported backend.mode={config.backend.mode}")

    sample_trace_ids = {
        prediction.sample_id: prediction.trace_ids[0]
        for prediction in predictions
        if prediction.trace_ids
    }
    return predictions, traces, sample_trace_ids
