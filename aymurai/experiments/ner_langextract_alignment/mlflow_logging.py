from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from statistics import median
from typing import Any

import mlflow

from aymurai.experiments.ner_langextract_alignment.compare import status_distribution
from aymurai.experiments.ner_langextract_alignment.config import NERLangExtractRunConfig
from aymurai.experiments.ner_langextract_alignment.types import LLMTrace
from aymurai.logger import get_logger
from aymurai.utils.yaml_data import save_yaml

logger = get_logger(__name__)


def configure_mlflow(config: NERLangExtractRunConfig) -> tuple[bool, str | None]:
    if not config.logging.mlflow.enabled:
        logger.warning("MLflow disabled by config (logging.mlflow.enabled=false).")
        return False, None

    # Keep MLflow initialization bounded to avoid long apparent freezes.
    timeout_s = max(1, int(round(float(config.logging.mlflow.request_timeout_s))))
    os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] = str(timeout_s)
    os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] = str(
        config.logging.mlflow.request_max_retries
    )

    logger.info(
        "Initializing MLflow: tracking_uri=%s experiment=%s timeout_s=%s retries=%s",
        config.logging.mlflow.tracking_uri,
        config.logging.mlflow.experiment_name,
        config.logging.mlflow.request_timeout_s,
        config.logging.mlflow.request_max_retries,
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

    # Keep explicit control of run ownership/experiment assignment by default.
    if config.logging.mlflow.enable_openai_autolog:
        try:
            mlflow.openai.autolog(log_traces=True, silent=True)
        except Exception:
            # Keep experiment execution resilient when autologging is unavailable.
            pass

    logger.info("MLflow ready: experiment_id=%s", experiment_id)
    return True, experiment_id


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int((len(sorted_vals) - 1) * p)
    return float(sorted_vals[idx])


def summarize_metrics(
    samples: list[dict[str, Any]], traces: list[LLMTrace]
) -> dict[str, float]:
    out: dict[str, float] = {}
    status_counts = status_distribution(samples)

    total = len(samples) or 1
    for status, count in status_counts.items():
        out[f"status_{status}_count"] = float(count)
        out[f"status_{status}_rate"] = float(count / total)

    agreement = status_counts.get("exact_match", 0)
    out["agreement_global_rate"] = float(agreement / total)

    label_seen: dict[str, int] = {}
    label_agreed: dict[str, int] = {}
    for sample in samples:
        exact_match = sample.get("comparison", {}).get("exact_match", [])
        partial_match = sample.get("comparison", {}).get("partial_match", [])
        only_ner = sample.get("comparison", {}).get("only_in_ner", [])
        only_lx = sample.get("comparison", {}).get("only_in_langextract", [])
        labels = {
            str(ent.get("label", "")).strip().upper()
            for ent in (exact_match + partial_match + only_ner + only_lx)
            if ent.get("label")
        }
        exact_matched_labels = {
            str(ent.get("label", "")).strip().upper()
            for ent in exact_match
            if ent.get("label")
        }
        for label in labels:
            label_seen[label] = label_seen.get(label, 0) + 1
        for label in exact_matched_labels:
            label_agreed[label] = label_agreed.get(label, 0) + 1

    for label, seen in label_seen.items():
        safe_label = label.lower()
        out[f"label_{safe_label}_coverage_count"] = float(seen)
        out[f"label_{safe_label}_agreement_rate"] = float(
            label_agreed.get(label, 0) / (seen or 1)
        )

    ner_lat = [float(s.get("latency_ms", {}).get("ner", 0.0)) for s in samples]
    lx_lat = [float(s.get("latency_ms", {}).get("langextract", 0.0)) for s in samples]

    out["latency_ner_p50_ms"] = float(median(ner_lat)) if ner_lat else 0.0
    out["latency_ner_p95_ms"] = _percentile(ner_lat, 0.95)
    out["latency_lx_p50_ms"] = float(median(lx_lat)) if lx_lat else 0.0
    out["latency_lx_p95_ms"] = _percentile(lx_lat, 0.95)

    flagged = sum(1 for s in samples if s.get("quality_flags"))
    out["samples_with_quality_flags"] = float(flagged)

    trace_errors = sum(1 for t in traces if t.error)
    skipped_empty_input = sum(
        1
        for t in traces
        if (t.error == "empty_or_invalid_input")
        or bool((t.metadata or {}).get("skipped_inference"))
    )
    out["llm_trace_count"] = float(len(traces))
    out["llm_trace_error_count"] = float(trace_errors)
    out["llm_trace_error_rate"] = float(trace_errors / (len(traces) or 1))
    out["skipped_empty_input_count"] = float(skipped_empty_input)
    out["skipped_empty_input_rate"] = float(skipped_empty_input / (len(samples) or 1))

    input_tokens = [
        int(t.metadata.get("token_input"))
        for t in traces
        if isinstance((t.metadata or {}).get("token_input"), int)
    ]
    output_tokens = [
        int(t.metadata.get("token_output"))
        for t in traces
        if isinstance((t.metadata or {}).get("token_output"), int)
    ]
    total_tokens = [
        int(t.metadata.get("token_total"))
        for t in traces
        if isinstance((t.metadata or {}).get("token_total"), int)
    ]

    out["llm_input_tokens_sum"] = float(sum(input_tokens))
    out["llm_output_tokens_sum"] = float(sum(output_tokens))
    out["llm_total_tokens_sum"] = float(sum(total_tokens))
    out["llm_input_tokens_avg"] = float(sum(input_tokens) / (len(input_tokens) or 1))
    out["llm_output_tokens_avg"] = float(sum(output_tokens) / (len(output_tokens) or 1))
    out["llm_total_tokens_avg"] = float(sum(total_tokens) / (len(total_tokens) or 1))

    return out


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")


def write_traces_summary_csv(path: Path, traces: list[LLMTrace]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
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
        writer.writeheader()
        for trace in traces:
            writer.writerow(
                {
                    "trace_id": trace.trace_id,
                    "sample_id": trace.sample_id,
                    "provider": trace.provider,
                    "model": trace.model,
                    "duration_ms": trace.duration_ms,
                    "token_input": (trace.metadata or {}).get("token_input", ""),
                    "token_output": (trace.metadata or {}).get("token_output", ""),
                    "token_total": (trace.metadata or {}).get("token_total", ""),
                    "error": trace.error or "",
                }
            )


def log_run_metadata(
    config: NERLangExtractRunConfig,
    *,
    run_name: str,
    mapping_hash: str,
    dataset_hash: str,
    metrics: dict[str, float],
) -> None:
    params = {
        "run_name": run_name,
        "provider": config.langextract.provider,
        "model": config.langextract.model_id,
        "api_base_url": config.api.base_url,
        "comparison_mode": config.comparison.mode,
        "mapping_hash": mapping_hash,
        "dataset_hash": dataset_hash,
        "qa_sample_rate": config.labelstudio.qa_sample_rate,
    }

    mlflow.log_params(params)
    mlflow.log_metrics(metrics)

    with tempfile.TemporaryDirectory() as temp_dir:
        tmp = Path(temp_dir)
        config_path = tmp / "config.yml"
        config_payload = config.model_dump(mode="json")
        save_yaml(config_payload, str(config_path))
        try:
            mlflow.log_artifact(str(config_path), artifact_path="config")
        except Exception as exc:
            logger.warning(f"Skipping MLflow artifact upload (config): {exc}")


def serialize_traces_for_logging(
    traces: list[LLMTrace],
    config: NERLangExtractRunConfig,
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


def safe_log_artifact(local_path: str, artifact_path: str | None = None) -> None:
    """Log artifact to MLflow without failing the run when artifact store is unavailable."""
    try:
        mlflow.log_artifact(local_path, artifact_path=artifact_path)
    except Exception as exc:
        logger.warning(
            f"Skipping MLflow artifact upload ({local_path} -> {artifact_path}): {exc}"
        )


def safe_log_artifacts(local_dir: str, artifact_path: str | None = None) -> None:
    """Log directory to MLflow without failing the run when artifact store is unavailable."""
    try:
        mlflow.log_artifacts(local_dir, artifact_path=artifact_path)
    except Exception as exc:
        logger.warning(
            f"Skipping MLflow artifacts upload ({local_dir} -> {artifact_path}): {exc}"
        )
