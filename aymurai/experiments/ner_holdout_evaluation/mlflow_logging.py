from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import mlflow
from mlflow.entities import Feedback
from mlflow.genai.judges import CategoricalRating

from aymurai.experiments.ner_langextract_alignment.types import LLMTrace
from aymurai.experiments.ner_holdout_evaluation.config import (
    NERHoldoutEvaluationConfig,
)
from aymurai.experiments.ner_holdout_evaluation.types import (
    FeedbackRecord,
    SampleScore,
)
from aymurai.logger import get_logger
from aymurai.utils.yaml_data import save_yaml

logger = get_logger(__name__)


def _append_feedback(
    *,
    feedback_records: list[FeedbackRecord],
    feedback_entities: list[Feedback],
    trace_id: str | None,
    sample_id: str,
    backend_mode: str,
    name: str,
    value: Any,
    rationale: str,
    perfect_span_set: bool | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    record_metadata = {
        "sample_id": sample_id,
        "backend_mode": backend_mode,
        **(metadata or {}),
    }
    feedback_records.append(
        FeedbackRecord(
            name=name,
            value=value,
            sample_id=sample_id,
            perfect_span_set=perfect_span_set,
            rationale=rationale,
            trace_id=trace_id,
            metadata=record_metadata,
        )
    )
    feedback_entities.append(
        Feedback(
            name=name,
            value=value,
            trace_id=trace_id,
            metadata=record_metadata,
            rationale=rationale,
        )
    )


def configure_mlflow(config: NERHoldoutEvaluationConfig) -> tuple[bool, str | None]:
    if not config.logging.mlflow.enabled:
        logger.warning("MLflow disabled by config (logging.mlflow.enabled=false).")
        return False, None

    timeout_s = max(1, int(round(float(config.logging.mlflow.request_timeout_s))))
    os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] = str(timeout_s)
    os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] = str(
        config.logging.mlflow.request_max_retries
    )

    mlflow.set_tracking_uri(config.logging.mlflow.tracking_uri)
    try:
        mlflow.set_experiment(config.logging.mlflow.experiment_name)
        experiment = mlflow.get_experiment_by_name(
            config.logging.mlflow.experiment_name
        )
        experiment_id = experiment.experiment_id if experiment else None
    except Exception as exc:
        logger.warning(
            "MLflow initialization failed; continuing without MLflow logging: %s", exc
        )
        return False, None

    if config.logging.mlflow.enable_openai_autolog:
        try:
            mlflow.openai.autolog(log_traces=True, silent=True)
        except Exception:
            pass

    return True, experiment_id


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_label_metrics_csv(
    path: Path, label_metrics: dict[str, dict[str, Any]]
) -> None:
    rows = []
    for label, stats in sorted(label_metrics.items()):
        rows.append(
            {
                "label": label,
                "tp": int(stats.get("tp", 0)),
                "fp": int(stats.get("fp", 0)),
                "fn": int(stats.get("fn", 0)),
                "support": int(stats.get("support", 0)),
                "precision": float(stats.get("precision", 0.0)),
                "recall": float(stats.get("recall", 0.0)),
                "f1": float(stats.get("f1", 0.0)),
            }
        )
    write_csv(
        path,
        rows,
        ["label", "tp", "fp", "fn", "support", "precision", "recall", "f1"],
    )


def _serialize_trace(
    trace: LLMTrace,
    *,
    log_prompt_text: bool,
    log_llm_outputs: bool,
    redact_sensitive_fields: bool,
) -> dict[str, Any]:
    payload = {
        "trace_id": trace.trace_id,
        "sample_id": trace.sample_id,
        "provider": trace.provider,
        "model": trace.model,
        "duration_ms": trace.duration_ms,
        "error": trace.error,
        "metadata": trace.metadata,
    }

    prompt = trace.prompt
    input_text = trace.input_text
    raw_output = trace.raw_output

    if redact_sensitive_fields:
        prompt = "[REDACTED]" if prompt else None
        input_text = "[REDACTED]" if input_text else None
        raw_output = "[REDACTED]" if raw_output else None

    payload["prompt"] = prompt if log_prompt_text else ""
    payload["input_text"] = input_text if log_prompt_text else ""
    payload["raw_output"] = raw_output if log_llm_outputs else ""
    payload["parsed_output"] = trace.parsed_output if log_llm_outputs else {}

    return payload


def serialize_traces_for_logging(
    traces: list[LLMTrace],
    config: NERHoldoutEvaluationConfig,
) -> list[dict[str, Any]]:
    return [
        _serialize_trace(
            trace,
            log_prompt_text=config.logging.privacy.log_prompt_text,
            log_llm_outputs=config.logging.privacy.log_llm_outputs,
            redact_sensitive_fields=config.logging.privacy.redact_sensitive_fields,
        )
        for trace in traces
    ]


def write_traces_summary_csv(path: Path, traces: list[LLMTrace]) -> None:
    rows = []
    for trace in traces:
        rows.append(
            {
                "trace_id": trace.trace_id,
                "sample_id": trace.sample_id,
                "provider": trace.provider,
                "model": trace.model,
                "duration_ms": float(trace.duration_ms),
                "token_input": (trace.metadata or {}).get("token_input", ""),
                "token_output": (trace.metadata or {}).get("token_output", ""),
                "token_total": (trace.metadata or {}).get("token_total", ""),
                "error": trace.error or "",
            }
        )

    write_csv(
        path,
        rows,
        [
            "trace_id",
            "sample_id",
            "provider",
            "model",
            "duration_ms",
            "token_input",
            "token_output",
            "token_total",
            "error",
        ],
    )


def build_feedback_records(
    sample_scores: list[SampleScore],
    *,
    sample_trace_ids: dict[str, str],
    backend_mode: str,
) -> tuple[list[FeedbackRecord], list[Feedback]]:
    feedback_records: list[FeedbackRecord] = []
    feedback_entities: list[Feedback] = []

    for score in sample_scores:
        categorical = (
            CategoricalRating.YES if score.perfect_span_set else CategoricalRating.NO
        )
        trace_id = sample_trace_ids.get(score.sample_id)
        base_metadata = {
            "perfect_definition": "span_set_exact",
            "tp": score.tp,
            "fp": score.fp,
            "fn": score.fn,
        }
        _append_feedback(
            feedback_records=feedback_records,
            feedback_entities=feedback_entities,
            trace_id=trace_id,
            sample_id=score.sample_id,
            backend_mode=backend_mode,
            name="perfect_prediction",
            value=str(categorical.value),
            rationale=(
                "Exact span set match"
                if score.perfect_span_set
                else "Exact span set mismatch"
            ),
            perfect_span_set=score.perfect_span_set,
            metadata=base_metadata,
        )

        _append_feedback(
            feedback_records=feedback_records,
            feedback_entities=feedback_entities,
            trace_id=trace_id,
            sample_id=score.sample_id,
            backend_mode=backend_mode,
            name="entity_match_rate",
            value=float(score.entity_match_rate or 0.0),
            rationale="Proportion of gold entities matched exactly (tp / gold_entities).",
            perfect_span_set=score.perfect_span_set,
            metadata=base_metadata,
        )
        _append_feedback(
            feedback_records=feedback_records,
            feedback_entities=feedback_entities,
            trace_id=trace_id,
            sample_id=score.sample_id,
            backend_mode=backend_mode,
            name="strict_precision",
            value=float(score.precision),
            rationale="Per-sample strict precision over exact span matches.",
            perfect_span_set=score.perfect_span_set,
            metadata=base_metadata,
        )
        _append_feedback(
            feedback_records=feedback_records,
            feedback_entities=feedback_entities,
            trace_id=trace_id,
            sample_id=score.sample_id,
            backend_mode=backend_mode,
            name="strict_recall",
            value=float(score.recall),
            rationale="Per-sample strict recall over exact span matches.",
            perfect_span_set=score.perfect_span_set,
            metadata=base_metadata,
        )
        _append_feedback(
            feedback_records=feedback_records,
            feedback_entities=feedback_entities,
            trace_id=trace_id,
            sample_id=score.sample_id,
            backend_mode=backend_mode,
            name="strict_f1",
            value=float(score.f1),
            rationale="Per-sample strict F1 over exact span matches.",
            perfect_span_set=score.perfect_span_set,
            metadata=base_metadata,
        )
        if score.token_relaxed_accuracy is not None:
            _append_feedback(
                feedback_records=feedback_records,
                feedback_entities=feedback_entities,
                trace_id=trace_id,
                sample_id=score.sample_id,
                backend_mode=backend_mode,
                name="token_relaxed_accuracy",
                value=float(score.token_relaxed_accuracy),
                rationale="Per-sample token-level relaxed accuracy.",
                perfect_span_set=score.perfect_span_set,
                metadata=base_metadata,
            )

    return feedback_records, feedback_entities


def log_feedback_to_mlflow(
    *,
    enabled: bool,
    feedback_records: list[FeedbackRecord],
) -> None:
    if not enabled:
        return

    for feedback in feedback_records:
        if not feedback.trace_id:
            continue
        try:
            mlflow.log_feedback(
                trace_id=feedback.trace_id,
                name=feedback.name,
                value=feedback.value,
                metadata=feedback.metadata,
                rationale=feedback.rationale,
            )
        except Exception as exc:
            logger.warning(
                "Skipping mlflow.log_feedback for sample_id=%s assessment=%s trace_id=%s: %s",
                feedback.sample_id,
                feedback.name,
                feedback.trace_id,
                exc,
            )


def log_run_metadata(
    config: NERHoldoutEvaluationConfig,
    *,
    run_name: str,
    model_name: str,
    dataset_hash: str,
    metrics: dict[str, float],
    config_path: str,
) -> None:
    params = {
        "run_name": run_name,
        "experiment_name": config.experiment.name,
        "backend_mode": config.backend.mode,
        "model": model_name,
        "data_format": config.data.format,
        "dataset_hash": dataset_hash,
        "perfect_definition": config.metrics.perfect_definition,
        "comparison_normalize_case": config.comparison.normalize_case,
        "comparison_normalize_accents": config.comparison.normalize_accents,
        "comparison_normalize_punctuation": config.comparison.normalize_punctuation,
    }

    mlflow.log_params(params)
    mlflow.log_metrics(metrics)

    with tempfile.TemporaryDirectory() as temp_dir:
        tmp = Path(temp_dir)
        config_out = tmp / "config.yaml"
        payload = config.model_dump(mode="json")

        if not config.logging.privacy.log_prompt_text and payload.get("langextract"):
            payload["langextract"]["prompt_description"] = ""

        save_yaml(payload, str(config_out))
        try:
            mlflow.log_artifact(str(config_out), artifact_path="config")
        except Exception as exc:
            logger.warning("Skipping config artifact upload: %s", exc)

        marker = tmp / "run_context.json"
        marker.write_text(
            json.dumps({"config_path": config_path, "run_name": run_name}, indent=2),
            encoding="utf-8",
        )
        safe_log_artifact(str(marker), artifact_path="config")


def safe_log_artifact(local_path: str, artifact_path: str | None = None) -> None:
    try:
        mlflow.log_artifact(local_path, artifact_path=artifact_path)
    except Exception as exc:
        logger.warning(
            "Skipping MLflow artifact upload (%s -> %s): %s",
            local_path,
            artifact_path,
            exc,
        )


def safe_log_artifacts(local_dir: str, artifact_path: str | None = None) -> None:
    try:
        mlflow.log_artifacts(local_dir, artifact_path=artifact_path)
    except Exception as exc:
        logger.warning(
            "Skipping MLflow artifacts upload (%s -> %s): %s",
            local_dir,
            artifact_path,
            exc,
        )
