from __future__ import annotations

import argparse
import hashlib
import json
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow

from aymurai.experiments.ner_holdout_evaluation.backends import iter_backend_inference
from aymurai.experiments.ner_holdout_evaluation.config import (
    NERHoldoutEvaluationConfig,
    load_experiment_config,
    render_run_name,
)
from aymurai.experiments.ner_holdout_evaluation.loaders import load_samples
from aymurai.experiments.ner_holdout_evaluation.metrics import evaluate_predictions
from aymurai.experiments.ner_holdout_evaluation.mlflow_logging import (
    build_feedback_records,
    configure_mlflow,
    log_feedback_to_mlflow,
    log_run_metadata,
    safe_log_artifact,
    safe_log_artifacts,
    serialize_traces_for_logging,
    write_csv,
    write_jsonl,
    write_label_metrics_csv,
    write_traces_summary_csv,
)
from aymurai.experiments.ner_holdout_evaluation.types import (
    feedback_to_dict,
    prediction_to_dict,
    sample_to_dict,
    score_to_dict,
)
from aymurai.experiments.ner_langextract_alignment.manifest import sha256_file
from aymurai.logger import get_logger

logger = get_logger(__name__)


def _resolve_model_name(config: NERHoldoutEvaluationConfig) -> str:
    if config.backend.mode == "langextract" and config.langextract is not None:
        return config.langextract.model_id
    return "anonymizer_api"


def _hash_text_rows(rows: list[str]) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(row.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _ensure_dirs(config: NERHoldoutEvaluationConfig) -> dict[str, Path]:
    base = Path(config.outputs.base_dir)
    base.mkdir(parents=True, exist_ok=True)

    paths = {
        "base": base,
        "samples_gold": base / config.outputs.samples_gold_jsonl,
        "predictions": base / config.outputs.predictions_jsonl,
        "sample_scores": base / config.outputs.per_sample_scores_jsonl,
        "metrics_summary": base / config.outputs.metrics_summary_json,
        "strict_label_metrics": base / config.outputs.strict_label_metrics_csv,
        "token_confusion": base / config.outputs.token_relaxed_confusion_csv,
        "feedback": base / config.outputs.feedback_jsonl,
        "traces_jsonl": base / config.outputs.traces_jsonl,
        "traces_csv": base / config.outputs.traces_summary_csv,
        "manifest": base / config.outputs.manifest_json,
    }

    (base / "reports").mkdir(parents=True, exist_ok=True)
    (base / "feedback").mkdir(parents=True, exist_ok=True)
    (base / "llm_traces").mkdir(parents=True, exist_ok=True)

    return paths


def _build_manifest(
    *,
    config: NERHoldoutEvaluationConfig,
    config_path: str,
    model_name: str,
    sample_count: int,
    prediction_count: int,
    trace_count: int,
) -> dict[str, Any]:
    input_path = Path(config.data.input_path)
    input_sha = (
        sha256_file(input_path) if input_path.exists() and input_path.is_file() else ""
    )
    config_sha = sha256_file(Path(config_path)) if Path(config_path).exists() else ""

    dataset_hash = _hash_text_rows(
        [
            config.data.format,
            str(input_path),
            input_sha,
            str(sample_count),
        ]
    )

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment": config.experiment.name,
        "backend_mode": config.backend.mode,
        "model": model_name,
        "data_format": config.data.format,
        "input_path": str(input_path),
        "input_sha256": input_sha,
        "config_path": config_path,
        "config_sha256": config_sha,
        "dataset_hash": dataset_hash,
        "samples_count": sample_count,
        "predictions_count": prediction_count,
        "llm_trace_count": trace_count,
    }


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_experiment(config_path: str) -> None:
    config = load_experiment_config(config_path)
    paths = _ensure_dirs(config)
    model_name = _resolve_model_name(config)
    mlflow_setup = configure_mlflow(config)
    if isinstance(mlflow_setup, tuple):
        mlflow_enabled, mlflow_experiment_id = mlflow_setup
    else:
        mlflow_enabled = bool(mlflow_setup)
        mlflow_experiment_id = None
    run_name = render_run_name(
        config.experiment.run_name,
        backend=config.backend.mode,
        model_name=model_name,
    )

    run_context = (
        mlflow.start_run(run_name=run_name, experiment_id=mlflow_experiment_id)
        if mlflow_enabled
        else nullcontext()
    )

    with run_context:
        if mlflow_enabled:
            mlflow.set_tags(
                {
                    "experiment_name": config.experiment.name,
                    "pipeline": "ner_holdout_evaluation",
                    "backend_mode": config.backend.mode,
                }
            )
            mlflow.log_param("config_path", config_path)
            mlflow.log_param("mlflow_experiment_id", mlflow_experiment_id or "")

        samples = load_samples(config)
        predictions = []
        traces = []
        sample_trace_ids: dict[str, str] = {}
        sample_scores = []
        feedback_records = []

        for sample, prediction, sample_traces in iter_backend_inference(
            samples, config
        ):
            predictions.append(prediction)
            traces.extend(sample_traces)

            if prediction.trace_ids:
                sample_trace_ids[sample.sample_id] = prediction.trace_ids[0]

            current_scores, _, _ = evaluate_predictions(
                [sample],
                [prediction],
                include_token_relaxed=config.metrics.include_token_relaxed,
            )
            current_score = current_scores[0]
            sample_scores.append(current_score)

            current_feedback_records, _ = build_feedback_records(
                [current_score],
                sample_trace_ids={
                    sample.sample_id: sample_trace_ids.get(sample.sample_id, "")
                },
                backend_mode=config.backend.mode,
            )
            feedback_records.extend(current_feedback_records)

            if mlflow_enabled and current_feedback_records:
                log_feedback_to_mlflow(
                    enabled=mlflow_enabled,
                    feedback_records=current_feedback_records,
                )

        _, summary, confusion_rows = evaluate_predictions(
            samples,
            predictions,
            include_token_relaxed=config.metrics.include_token_relaxed,
        )

        manifest = _build_manifest(
            config=config,
            config_path=config_path,
            model_name=model_name,
            sample_count=len(samples),
            prediction_count=len(predictions),
            trace_count=len(traces),
        )

        serialized_predictions = [prediction_to_dict(pred) for pred in predictions]
        if not config.logging.privacy.log_raw_predictions:
            for row in serialized_predictions:
                row["raw_payload"] = {}

        write_jsonl(
            paths["samples_gold"], [sample_to_dict(sample) for sample in samples]
        )
        write_jsonl(paths["predictions"], serialized_predictions)
        write_jsonl(
            paths["sample_scores"], [score_to_dict(score) for score in sample_scores]
        )
        write_jsonl(
            paths["feedback"], [feedback_to_dict(record) for record in feedback_records]
        )

        write_label_metrics_csv(
            paths["strict_label_metrics"], summary.strict_label_metrics
        )
        write_csv(
            paths["token_confusion"],
            confusion_rows,
            ["gold_label", "pred_label", "count"],
        )

        if traces:
            serialized_traces = serialize_traces_for_logging(traces, config)
            write_jsonl(paths["traces_jsonl"], serialized_traces)
            write_traces_summary_csv(paths["traces_csv"], traces)

        metrics_payload = {
            "metrics": summary.metrics,
            "strict_label_metrics": summary.strict_label_metrics,
            "token_relaxed_label_metrics": summary.token_relaxed_label_metrics,
            "token_relaxed_micro": summary.token_relaxed_micro,
        }
        _save_json(paths["metrics_summary"], metrics_payload)
        _save_json(paths["manifest"], manifest)

        if mlflow_enabled:
            log_run_metadata(
                config,
                run_name=run_name,
                model_name=model_name,
                dataset_hash=manifest["dataset_hash"],
                metrics=summary.metrics,
                config_path=config_path,
            )

            safe_log_artifact(str(paths["samples_gold"]), artifact_path="data")
            safe_log_artifact(str(paths["predictions"]), artifact_path="predictions")
            safe_log_artifact(str(paths["sample_scores"]), artifact_path="metrics")
            safe_log_artifact(str(paths["feedback"]), artifact_path="feedback")
            safe_log_artifact(
                str(paths["strict_label_metrics"]), artifact_path="reports"
            )
            safe_log_artifact(str(paths["token_confusion"]), artifact_path="reports")
            safe_log_artifact(str(paths["metrics_summary"]), artifact_path="metrics")
            safe_log_artifact(str(paths["manifest"]), artifact_path="data")

            if traces:
                safe_log_artifact(
                    str(paths["traces_jsonl"]), artifact_path="llm_traces"
                )
                safe_log_artifact(str(paths["traces_csv"]), artifact_path="llm_traces")

            safe_log_artifacts(
                str(paths["base"] / "reports"), artifact_path="reports_dir"
            )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run NER/LangExtract holdout evaluation experiment from YAML config."
    )
    parser.add_argument(
        "--config", required=True, help="Path to experiment YAML config"
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    run_experiment(args.config)


if __name__ == "__main__":
    main()
