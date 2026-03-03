from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import mlflow
import requests
from tqdm import tqdm

from aymurai.experiments.ner_holdout_evaluation.config import NERHoldoutEvaluationConfig
from aymurai.experiments.ner_holdout_evaluation.types import (
    BackendPrediction,
    CanonicalSample,
    CanonicalSpan,
)
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
from aymurai.transforms.anonymization_postprocess.core import clean_entity_boundaries
from aymurai.utils.yaml_data import load_yaml

BackendInferenceResult = tuple[CanonicalSample, BackendPrediction, list[LLMTrace]]


def _serialize_trace_payload(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


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
        attrs = {}
        if isinstance(entity.extra, dict):
            attrs = entity.extra.get("attrs") or {}
        base_text = str(attrs.get("aymurai_alt_text") or entity.text)
        base_start = attrs.get("aymurai_alt_start_char")
        base_end = attrs.get("aymurai_alt_end_char")
        start_char = (
            int(base_start) if isinstance(base_start, int) else int(entity.start_char)
        )
        end_char = int(base_end) if isinstance(base_end, int) else int(entity.end_char)
        cleaned = clean_entity_boundaries(
            base_text,
            start_char=start_char,
            end_char=end_char,
        )
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
                normalized_text=(
                    str(cleaned["text"])
                    if cleaned is not None
                    else str(entity.normalized_text or entity.text)
                ),
                alt_start_char=(
                    int(cleaned["start_char"]) if cleaned is not None else start_char
                ),
                alt_end_char=int(cleaned["end_char"])
                if cleaned is not None
                else end_char,
                extra=dict(entity.extra or {}),
            )
        )
    return spans


def _infer_ner_model_name(payload: dict[str, Any]) -> str:
    methods = {
        str((label.get("attrs") or {}).get("aymurai_method")).strip()
        for label in payload.get("labels", [])
        if (label.get("attrs") or {}).get("aymurai_method")
    }
    return methods.pop() if len(methods) == 1 else "anonymizer_api"


def _canonical_sample_inputs(sample: CanonicalSample) -> dict[str, str]:
    return {
        "sample_id": sample.sample_id,
        "text": str(sample.text or ""),
    }


def _canonical_prediction_outputs(prediction: BackendPrediction) -> dict[str, Any]:
    return {
        "latency_ms": float(prediction.latency_ms),
        "error": prediction.error,
        "quality_flags": list(prediction.quality_flags),
        "spans": [
            {
                "label": span.label,
                "start": int(span.start),
                "end": int(span.end),
                "text": span.normalized_text or span.text,
            }
            for span in prediction.spans
        ],
    }


def _sample_trace_attributes(
    sample: CanonicalSample,
    prediction: BackendPrediction,
    config: NERHoldoutEvaluationConfig,
) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "sample_id": sample.sample_id,
        "backend_mode": prediction.backend_mode,
        "text_length": len(str(sample.text or "")),
        "latency_ms": float(prediction.latency_ms),
        "span_count": len(prediction.spans),
        "quality_flags": list(prediction.quality_flags),
    }

    if prediction.error:
        attributes["error"] = prediction.error

    if prediction.backend_mode == "ner_api":
        attributes.update(
            {
                "endpoint": config.api.anonymizer_predict_path,
                "use_cache": config.api.use_cache,
            }
        )
    elif config.langextract is not None:
        attributes.update(
            {
                "provider": config.langextract.provider,
                "model_id": config.langextract.model_id,
                "extraction_passes": config.langextract.extraction_passes,
                "batch_length": config.langextract.batch_length,
            }
        )

    return attributes


def _predict_ner_api_sample(
    sample: CanonicalSample,
    config: NERHoldoutEvaluationConfig,
    *,
    label_mapping: dict[str, str],
    session: requests.Session,
) -> BackendInferenceResult:
    text = str(sample.text or "")
    if not text.strip():
        return (
            sample,
            BackendPrediction(
                sample_id=sample.sample_id,
                backend_mode="ner_api",
                spans=[],
                latency_ms=0.0,
                error="empty_or_invalid_input",
                quality_flags=["empty_or_invalid_input"],
                raw_payload={"labels": []},
            ),
            [],
        )

    request_payload = {
        "sample_id": sample.sample_id,
        "text": text,
        "use_cache": config.api.use_cache,
        "path": config.api.anonymizer_predict_path,
    }

    if mlflow.active_run() is not None:
        with mlflow.start_span(
            name="ner_api.predict",
            span_type="TOOL",
            attributes={
                "sample_id": sample.sample_id,
                "backend_mode": "ner_api",
                "endpoint": config.api.anonymizer_predict_path,
                "use_cache": config.api.use_cache,
            },
        ) as span:
            span.set_inputs(request_payload)
            payload: dict[str, Any] | None = None
            latency_ms = 0.0
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
                model_name = _infer_ner_model_name(payload)
                trace_id = span.request_id or span.trace_id
                trace_metadata = {
                    "backend_mode": "ner_api",
                    "endpoint": config.api.anonymizer_predict_path,
                    "use_cache": config.api.use_cache,
                    "latency_ms": float(latency_ms),
                    "label_count": len(payload.get("labels", [])),
                    "entity_count": len(spans),
                    "quality_flags": sorted(set(flags)),
                }
                span.set_outputs(payload)
                span.set_attributes(trace_metadata)
                trace = LLMTrace(
                    trace_id=trace_id,
                    sample_id=sample.sample_id,
                    provider="aymurai",
                    model=model_name,
                    prompt="",
                    input_text=text,
                    raw_output=_serialize_trace_payload(payload),
                    parsed_output=payload,
                    duration_ms=float(latency_ms),
                    error=None,
                    metadata=trace_metadata,
                )
                return (
                    sample,
                    BackendPrediction(
                        sample_id=sample.sample_id,
                        backend_mode="ner_api",
                        spans=spans,
                        latency_ms=float(latency_ms),
                        error=None,
                        quality_flags=list(flags),
                        raw_payload=payload,
                        trace_ids=[trace_id],
                    ),
                    [trace],
                )
            except Exception as exc:
                error_payload = payload or {"labels": []}
                trace_id = span.request_id or span.trace_id
                trace_metadata = {
                    "backend_mode": "ner_api",
                    "endpoint": config.api.anonymizer_predict_path,
                    "use_cache": config.api.use_cache,
                    "latency_ms": float(latency_ms),
                    "quality_flags": ["ner_api_inference_error"],
                }
                span.record_exception(exc)
                span.set_outputs({"error": str(exc), **error_payload})
                span.set_attributes(trace_metadata)
                trace = LLMTrace(
                    trace_id=trace_id,
                    sample_id=sample.sample_id,
                    provider="aymurai",
                    model=_infer_ner_model_name(error_payload),
                    prompt="",
                    input_text=text,
                    raw_output=_serialize_trace_payload(
                        {"error": str(exc), **error_payload}
                    ),
                    parsed_output={"error": str(exc), **error_payload},
                    duration_ms=float(latency_ms),
                    error=str(exc),
                    metadata=trace_metadata,
                )
                return (
                    sample,
                    BackendPrediction(
                        sample_id=sample.sample_id,
                        backend_mode="ner_api",
                        spans=[],
                        latency_ms=float(latency_ms),
                        error=str(exc),
                        quality_flags=["ner_api_inference_error"],
                        raw_payload={"labels": []},
                        trace_ids=[trace_id],
                    ),
                    [trace],
                )

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
        return (
            sample,
            BackendPrediction(
                sample_id=sample.sample_id,
                backend_mode="ner_api",
                spans=spans,
                latency_ms=float(latency_ms),
                error=None,
                quality_flags=list(flags),
                raw_payload=payload,
                trace_ids=[],
            ),
            [],
        )
    except Exception as exc:
        return (
            sample,
            BackendPrediction(
                sample_id=sample.sample_id,
                backend_mode="ner_api",
                spans=[],
                latency_ms=0.0,
                error=str(exc),
                quality_flags=["ner_api_inference_error"],
                raw_payload={"labels": []},
                trace_ids=[],
            ),
            [],
        )


def _predict_langextract_sample(
    sample: CanonicalSample,
    config: NERHoldoutEvaluationConfig,
    *,
    label_mapping: dict[str, str],
    examples: list[Any],
    model: Any,
) -> BackendInferenceResult:
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
        return (
            sample,
            BackendPrediction(
                sample_id=sample.sample_id,
                backend_mode="langextract",
                spans=spans,
                latency_ms=float(latency_ms),
                error=str(payload.get("error")) if payload.get("error") else None,
                quality_flags=sorted(set(flags)),
                raw_payload=payload,
                trace_ids=trace_ids,
            ),
            sample_traces,
        )
    except Exception as exc:
        return (
            sample,
            BackendPrediction(
                sample_id=sample.sample_id,
                backend_mode="langextract",
                spans=[],
                latency_ms=0.0,
                error=str(exc),
                quality_flags=["langextract_inference_error"],
                raw_payload={"extractions": []},
                trace_ids=[],
            ),
            [],
        )


def iter_backend_inference(
    samples: list[CanonicalSample],
    config: NERHoldoutEvaluationConfig,
) -> Iterator[BackendInferenceResult]:
    label_mapping = _load_label_mapping(config.mapping.labels_yaml_path)

    if config.backend.mode == "ner_api":
        session = requests.Session()
        try:
            for sample in tqdm(samples, desc="infer-ner-api", unit="sample"):
                if mlflow.active_run() is None:
                    yield _predict_ner_api_sample(
                        sample,
                        config,
                        label_mapping=label_mapping,
                        session=session,
                    )
                    continue

                with mlflow.start_span(
                    name="holdout.sample",
                    span_type="TASK",
                    attributes={
                        "sample_id": sample.sample_id,
                        "backend_mode": config.backend.mode,
                    },
                ) as sample_span:
                    sample_span.set_inputs(_canonical_sample_inputs(sample))
                    result = _predict_ner_api_sample(
                        sample,
                        config,
                        label_mapping=label_mapping,
                        session=session,
                    )
                    _, prediction, sample_traces = result
                    sample_trace_id = sample_span.request_id or sample_span.trace_id
                    prediction.trace_ids = [
                        sample_trace_id,
                        *[
                            trace_id
                            for trace_id in prediction.trace_ids
                            if trace_id != sample_trace_id
                        ],
                    ]
                    sample_span.set_outputs(_canonical_prediction_outputs(prediction))
                    sample_span.set_attributes(
                        _sample_trace_attributes(sample, prediction, config)
                    )
                    if prediction.error:
                        sample_span.set_status("ERROR")
                    yield sample, prediction, sample_traces
        finally:
            session.close()
        return

    if config.langextract is None:
        raise ValueError("langextract config is required when backend.mode=langextract")
    examples = load_examples_from_yaml(config.langextract.examples_yaml_path)
    if not examples:
        raise ValueError(
            f"No examples loaded from {config.langextract.examples_yaml_path}"
        )
    model = build_tracing_model(config.langextract)
    for sample in tqdm(samples, desc="infer-langextract", unit="sample"):
        if mlflow.active_run() is None:
            yield _predict_langextract_sample(
                sample,
                config,
                label_mapping=label_mapping,
                examples=examples,
                model=model,
            )
            continue

        with mlflow.start_span(
            name="holdout.sample",
            span_type="TASK",
            attributes={
                "sample_id": sample.sample_id,
                "backend_mode": config.backend.mode,
            },
        ) as sample_span:
            sample_span.set_inputs(_canonical_sample_inputs(sample))
            result = _predict_langextract_sample(
                sample,
                config,
                label_mapping=label_mapping,
                examples=examples,
                model=model,
            )
            _, prediction, sample_traces = result
            sample_trace_id = sample_span.request_id or sample_span.trace_id
            prediction.trace_ids = [
                sample_trace_id,
                *[
                    trace_id
                    for trace_id in prediction.trace_ids
                    if trace_id != sample_trace_id
                ],
            ]
            sample_span.set_outputs(_canonical_prediction_outputs(prediction))
            sample_span.set_attributes(
                _sample_trace_attributes(sample, prediction, config)
            )
            if prediction.error:
                sample_span.set_status("ERROR")
            yield sample, prediction, sample_traces


def run_backend_inference(
    samples: list[CanonicalSample],
    config: NERHoldoutEvaluationConfig,
) -> tuple[list[BackendPrediction], list[LLMTrace], dict[str, str]]:
    predictions: list[BackendPrediction] = []
    traces: list[LLMTrace] = []
    for _, prediction, sample_traces in iter_backend_inference(samples, config):
        predictions.append(prediction)
        traces.extend(sample_traces)

    sample_trace_ids = {
        prediction.sample_id: prediction.trace_ids[0]
        for prediction in predictions
        if prediction.trace_ids
    }
    return predictions, traces, sample_trace_ids
