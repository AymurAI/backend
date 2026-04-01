from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow
from flair.data import Sentence
from flair.datasets import ColumnCorpus
from flair.models import SequenceTagger
from mlflow.tracking import MlflowClient

from aymurai.experiments.ner_flair_finetunning.config import (
    NERFinetuningConfig,
    load_experiment_config,
    render_run_name,
)
from aymurai.experiments.ner_flair_finetunning.loaders import (
    build_span_comparison_row,
    flair_to_prediction,
    sentence_to_canonical_sample,
)
from aymurai.experiments.ner_flair_finetunning.metrics import evaluate_predictions
from aymurai.experiments.ner_flair_finetunning.mlflow_logging import (
    configure_mlflow,
    log_run_metadata,
    log_span_comparison_trace,
    log_training_curves_from_tsv,
    start_live_training_logging,
    safe_log_artifact,
    safe_log_artifacts,
    safe_log_metrics,
    write_csv,
    write_comparisons_html,
    write_json,
    write_jsonl,
    write_label_metrics_csv,
)
from aymurai.experiments.ner_flair_finetunning.train import (
    build_stacked_tagger,
    execute_training,
)
from aymurai.experiments.ner_flair_finetunning.types import (
    prediction_to_dict,
    sample_to_dict,
    score_to_dict,
)
from aymurai.logger import get_logger

logger = get_logger(__name__)


def _resolve_model_name(config: NERFinetuningConfig) -> str:
    if config.backend.mode == "pretrained_flair" and config.flair_model.finetune_from:
        return config.flair_model.finetune_from
    return config.flair_model.model_id


def _hash_text_rows(rows: list[str]) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(row.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _ensure_dirs(config: NERFinetuningConfig) -> dict[str, Path]:
    base = Path(config.outputs.base_dir)
    base.mkdir(parents=True, exist_ok=True)

    paths = {
        "base": base,
        "manifest": base / config.outputs.manifest_json,
        "dev_root": base / "dev_epochs",
        "test_root": base / "test_final",
        "best_model": base / "best-model.pt",
        "final_model": base / "final-model.pt",
        "loss_tsv": base / "loss.tsv",
    }

    paths["dev_root"].mkdir(parents=True, exist_ok=True)
    paths["test_root"].mkdir(parents=True, exist_ok=True)
    (base / "reports").mkdir(parents=True, exist_ok=True)

    return paths


def _sanitize_path_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "run"


def _resolve_run_output_base(config: NERFinetuningConfig, run_name: str) -> Path:
    base = Path(config.outputs.base_dir)
    if not config.outputs.create_run_subdir:
        return base

    raw_subdir = config.outputs.run_subdir_template.format(
        run_name=run_name,
        timestamp=datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S"),
    )
    subdir = _sanitize_path_component(raw_subdir)
    candidate = base / subdir
    if not candidate.exists():
        return candidate

    suffix = datetime.now(timezone.utc).strftime("%H%M%S")
    return base / f"{subdir}_{suffix}"


def _build_manifest(
    *,
    config: NERFinetuningConfig,
    config_path: str,
    model_name: str,
    train_metrics_by_epoch: dict[int, dict[str, float]],
    dev_epochs: list[int],
) -> dict[str, Any]:
    dataset_hash = _hash_text_rows(
        [
            config.data.input_path,
            config.data.train_file,
            config.data.dev_file,
            config.data.test_file,
            model_name,
            str(config.training.max_epochs),
            str(config.training.learning_rate),
        ]
    )

    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "experiment": config.experiment.name,
        "backend_mode": config.backend.mode,
        "model": model_name,
        "config_path": config_path,
        "dataset_root": config.data.input_path,
        "dataset_hash": dataset_hash,
        "max_epochs": config.training.max_epochs,
        "logged_training_epochs": sorted(train_metrics_by_epoch.keys()),
        "evaluated_dev_epochs": sorted(dev_epochs),
    }


def _snapshot_for_prediction(sentence: Sentence) -> Sentence:
    token_texts = [token.text for token in sentence.tokens]
    if token_texts:
        return Sentence(token_texts, use_tokenizer=False)
    return Sentence(sentence.to_plain_string(), use_tokenizer=True)


def _checkpoint_epoch(path: Path) -> int | None:
    digits = "".join(ch if ch.isdigit() else " " for ch in path.stem).split()
    if not digits:
        return None
    try:
        return int(digits[-1])
    except ValueError:
        return None


def _find_epoch_checkpoints(base_dir: Path) -> dict[int, Path]:
    candidates: list[Path] = []
    candidates.extend(base_dir.glob("model_epoch_*.pt"))
    candidates.extend(base_dir.glob("*epoch*.pt"))

    out: dict[int, Path] = {}
    for path in sorted(set(candidates)):
        epoch = _checkpoint_epoch(path)
        if epoch is None:
            continue
        out[epoch] = path
    return out


def _should_eval_dev_epoch(
    *,
    epoch: int,
    start_epoch: int,
    every_k_epochs: int,
) -> bool:
    start = max(1, int(start_epoch))
    step = max(1, int(every_k_epochs))
    if epoch < start:
        return False
    return (epoch - start) % step == 0


def _split_paths(root: Path, config: NERFinetuningConfig) -> dict[str, Path]:
    return {
        "samples_gold": root / config.outputs.samples_gold_jsonl,
        "predictions": root / config.outputs.predictions_jsonl,
        "sample_scores": root / config.outputs.per_sample_scores_jsonl,
        "comparisons": root / config.outputs.comparisons_jsonl,
        "comparisons_csv": root / config.outputs.comparisons_csv,
        "comparisons_html": root / config.outputs.comparisons_html,
        "metrics_summary": root / config.outputs.metrics_summary_json,
        "strict_label_metrics": root / config.outputs.strict_label_metrics_csv,
        "token_confusion": root / config.outputs.token_relaxed_confusion_csv,
    }


def _start_live_dev_checkpoint_evaluator(
    *,
    base_path: Path,
    dev_root: Path,
    dev_sentences: list[Sentence],
    backend_mode: str,
    config: NERFinetuningConfig,
    evaluated_epochs: set[int],
    evaluated_lock: threading.Lock,
    run_id: str | None,
    mlflow_enabled: bool,
    poll_interval_s: float = 20.0,
) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    client = MlflowClient() if mlflow_enabled and run_id else None

    def _worker() -> None:
        while not stop_event.is_set():
            try:
                checkpoint_paths = _find_epoch_checkpoints(base_path)
                for epoch, checkpoint in sorted(checkpoint_paths.items()):
                    with evaluated_lock:
                        if epoch in evaluated_epochs:
                            continue

                    if not _should_eval_dev_epoch(
                        epoch=epoch,
                        start_epoch=config.training.dev_eval_start_epoch,
                        every_k_epochs=config.training.dev_eval_every_k_epochs,
                    ):
                        continue

                    model = SequenceTagger.load(checkpoint)
                    dev_dir = dev_root / f"epoch_{epoch:03d}"
                    try:
                        eval_result = _evaluate_split(
                            model=model,
                            split_name="dev",
                            split_sentences=dev_sentences,
                            backend_mode=backend_mode,
                            config=config,
                            out_dir=dev_dir,
                            epoch=epoch,
                            trace_logging_enabled=(
                                mlflow_enabled
                                and config.logging.mlflow.enable_span_comparison_traces
                            ),
                            trace_max_samples=config.logging.mlflow.max_traces_per_split,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Skipping live dev evaluation for epoch %s due to error: %s",
                            epoch,
                            exc,
                        )
                        continue

                    with evaluated_lock:
                        evaluated_epochs.add(epoch)

                    if client and run_id:
                        for key, value in eval_result["metrics"].items():
                            client.log_metric(
                                run_id=run_id,
                                key=f"dev_{key}",
                                value=float(value),
                                step=int(epoch),
                            )
                        try:
                            client.log_artifacts(
                                run_id=run_id,
                                local_dir=str(dev_dir),
                                artifact_path=f"dev_epochs/epoch_{epoch:03d}",
                            )
                        except Exception as exc:
                            logger.warning(
                                "Skipping live dev artifact upload for epoch %s: %s",
                                epoch,
                                exc,
                            )
            except Exception as exc:
                logger.warning(
                    "Live dev checkpoint evaluation skipped in this poll: %s", exc
                )

            stop_event.wait(max(3.0, float(poll_interval_s)))

    thread = threading.Thread(
        target=_worker,
        name="live-dev-checkpoint-evaluator",
        daemon=True,
    )
    thread.start()
    return stop_event, thread


def _evaluate_split(
    *,
    model: SequenceTagger,
    split_name: str,
    split_sentences: list[Sentence],
    backend_mode: str,
    config: NERFinetuningConfig,
    out_dir: Path,
    epoch: int | None,
    trace_logging_enabled: bool = False,
    trace_max_samples: int | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    split_paths = _split_paths(out_dir, config)

    gold_samples = []
    predictions = []
    comparisons = []

    for i, sentence in enumerate(split_sentences):
        sample_id = f"{split_name}_{i}"
        gold_sample = sentence_to_canonical_sample(sentence, sample_id)

        pred_sentence = _snapshot_for_prediction(sentence)
        model.predict(pred_sentence)
        prediction = flair_to_prediction(
            pred_sentence,
            sample_id,
            backend_mode=backend_mode,
        )

        gold_samples.append(gold_sample)
        predictions.append(prediction)
        comparisons.append(
            build_span_comparison_row(
                gold_sample,
                prediction,
                split=split_name,
                epoch=epoch,
            )
        )
        comparison_row = comparisons[-1]
        within_trace_budget = trace_max_samples is None or i < int(trace_max_samples)
        if trace_logging_enabled and within_trace_budget:
            log_span_comparison_trace(
                enabled=True,
                split_name=split_name,
                sample_id=sample_id,
                epoch=epoch,
                text=gold_sample.text,
                gold_spans=comparison_row["gold_spans"],
                predicted_spans=comparison_row["predicted_spans"],
                false_negatives=comparison_row["false_negatives"],
                false_positives=comparison_row["false_positives"],
                perfect_span_set=bool(comparison_row["perfect_span_set"]),
            )

    sample_scores, summary, confusion_rows = evaluate_predictions(
        gold_samples,
        predictions,
        include_token_relaxed=config.metrics.include_token_relaxed,
    )

    write_jsonl(split_paths["samples_gold"], [sample_to_dict(s) for s in gold_samples])
    write_jsonl(
        split_paths["predictions"], [prediction_to_dict(p) for p in predictions]
    )
    write_jsonl(split_paths["sample_scores"], [score_to_dict(s) for s in sample_scores])
    write_jsonl(split_paths["comparisons"], comparisons)
    write_comparisons_html(
        split_paths["comparisons_html"],
        split_name=f"{split_name} (epoch={epoch if epoch is not None else 'final'})",
        comparisons=comparisons,
    )
    write_csv(
        split_paths["comparisons_csv"],
        [
            {
                "sample_id": row["sample_id"],
                "split": row["split"],
                "epoch": "" if row["epoch"] is None else int(row["epoch"]),
                "text": row["text"],
                "perfect_span_set": bool(row["perfect_span_set"]),
                "gold_spans_count": len(row["gold_spans"]),
                "predicted_spans_count": len(row["predicted_spans"]),
                "false_negatives_count": len(row["false_negatives"]),
                "false_positives_count": len(row["false_positives"]),
                "gold_spans": json.dumps(row["gold_spans"], ensure_ascii=False),
                "predicted_spans": json.dumps(
                    row["predicted_spans"], ensure_ascii=False
                ),
                "false_negatives": json.dumps(
                    row["false_negatives"], ensure_ascii=False
                ),
                "false_positives": json.dumps(
                    row["false_positives"], ensure_ascii=False
                ),
            }
            for row in comparisons
        ],
        [
            "sample_id",
            "split",
            "epoch",
            "text",
            "perfect_span_set",
            "gold_spans_count",
            "predicted_spans_count",
            "false_negatives_count",
            "false_positives_count",
            "gold_spans",
            "predicted_spans",
            "false_negatives",
            "false_positives",
        ],
    )

    metrics_payload = {
        "metrics": summary.metrics,
        "strict_label_metrics": summary.strict_label_metrics,
        "token_relaxed_label_metrics": summary.token_relaxed_label_metrics,
        "token_relaxed_micro": summary.token_relaxed_micro,
    }
    write_json(split_paths["metrics_summary"], metrics_payload)
    write_label_metrics_csv(
        split_paths["strict_label_metrics"], summary.strict_label_metrics
    )
    write_csv(
        split_paths["token_confusion"],
        confusion_rows,
        ["gold_label", "pred_label", "count"],
    )

    return {
        "metrics": summary.metrics,
        "paths": split_paths,
        "sample_count": len(gold_samples),
    }


def run_experiment(config_path: str) -> None:
    config = load_experiment_config(config_path)
    model_name = _resolve_model_name(config)
    run_name = render_run_name(
        config.experiment.run_name,
        backend=config.backend.mode,
        model_name=model_name,
    )
    run_output_base = _resolve_run_output_base(config, run_name)
    config.outputs.base_dir = str(run_output_base)
    paths = _ensure_dirs(config)

    columns = {0: "text", 1: "ner"}
    corpus = ColumnCorpus(
        config.data.input_path,
        columns,
        train_file=config.data.train_file,
        test_file=config.data.test_file,
        dev_file=config.data.dev_file,
    )

    mlflow_enabled, mlflow_experiment_id = configure_mlflow(config)
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
                    "pipeline": "ner_flair_finetuning",
                    "backend_mode": config.backend.mode,
                    "base_model": model_name,
                }
            )

        run_id = (
            mlflow.active_run().info.run_id
            if mlflow_enabled and mlflow.active_run()
            else None
        )

        live_stop, live_thread = start_live_training_logging(
            paths["base"],
            enabled=mlflow_enabled,
            run_id=run_id,
        )
        evaluated_epochs_live: set[int] = set()
        evaluated_lock = threading.Lock()
        live_dev_stop, live_dev_thread = _start_live_dev_checkpoint_evaluator(
            base_path=paths["base"],
            dev_root=paths["dev_root"],
            dev_sentences=list(corpus.dev),
            backend_mode=config.backend.mode,
            config=config,
            evaluated_epochs=evaluated_epochs_live,
            evaluated_lock=evaluated_lock,
            run_id=run_id,
            mlflow_enabled=mlflow_enabled,
        )
        try:
            tagger = build_stacked_tagger(corpus, config.flair_model)
            execute_training(tagger, corpus, config.training, paths["base"])
        finally:
            if live_stop is not None:
                live_stop.set()
            if live_thread is not None:
                live_thread.join(timeout=15)
            live_dev_stop.set()
            live_dev_thread.join(timeout=20)

        train_metrics_by_epoch = log_training_curves_from_tsv(
            paths["base"], enabled=False
        )

        checkpoint_paths = _find_epoch_checkpoints(paths["base"])
        with evaluated_lock:
            evaluated_epochs: list[int] = sorted(evaluated_epochs_live)

        model_for_test_path: Path | None = None
        if config.training.test_eval_epoch is not None:
            selected_epoch = int(config.training.test_eval_epoch)
            model_for_test_path = checkpoint_paths.get(selected_epoch)
            if model_for_test_path is None:
                raise FileNotFoundError(
                    f"Configured training.test_eval_epoch={selected_epoch}, but no checkpoint for that epoch was found."
                )

        if model_for_test_path is None:
            model_for_test_path = (
                paths["best_model"]
                if paths["best_model"].exists()
                else paths["final_model"]
            )
            if not model_for_test_path.exists():
                raise FileNotFoundError(
                    "No trained model found. Expected best-model.pt or final-model.pt in output dir."
                )

        if checkpoint_paths:
            for epoch, checkpoint in sorted(checkpoint_paths.items()):
                if epoch in evaluated_epochs:
                    continue
                if not _should_eval_dev_epoch(
                    epoch=epoch,
                    start_epoch=config.training.dev_eval_start_epoch,
                    every_k_epochs=config.training.dev_eval_every_k_epochs,
                ):
                    continue
                model = SequenceTagger.load(checkpoint)
                dev_dir = paths["dev_root"] / f"epoch_{epoch:03d}"
                try:
                    eval_result = _evaluate_split(
                        model=model,
                        split_name="dev",
                        split_sentences=list(corpus.dev),
                        backend_mode=config.backend.mode,
                        config=config,
                        out_dir=dev_dir,
                        epoch=epoch,
                        trace_logging_enabled=(
                            mlflow_enabled
                            and config.logging.mlflow.enable_span_comparison_traces
                        ),
                        trace_max_samples=config.logging.mlflow.max_traces_per_split,
                    )
                except Exception as exc:
                    logger.warning(
                        "Skipping post-train dev evaluation for epoch %s due to error: %s",
                        epoch,
                        exc,
                    )
                    continue
                evaluated_epochs.append(epoch)

                if mlflow_enabled:
                    safe_log_metrics(
                        {f"dev_{k}": v for k, v in eval_result["metrics"].items()},
                        step=epoch,
                    )
                    safe_log_artifacts(
                        str(dev_dir), artifact_path=f"dev_epochs/epoch_{epoch:03d}"
                    )
        if not evaluated_epochs:
            fallback_epoch = (
                max(train_metrics_by_epoch)
                if train_metrics_by_epoch
                else int(config.training.max_epochs)
            )
            logger.warning(
                "No eligible dev checkpoints found. Running dev evaluation once with %s.",
                model_for_test_path.name,
            )
            fallback_model = SequenceTagger.load(model_for_test_path)
            dev_dir = paths["dev_root"] / f"epoch_{fallback_epoch:03d}_fallback"
            eval_result = _evaluate_split(
                model=fallback_model,
                split_name="dev",
                split_sentences=list(corpus.dev),
                backend_mode=config.backend.mode,
                config=config,
                out_dir=dev_dir,
                epoch=fallback_epoch,
                trace_logging_enabled=(
                    mlflow_enabled
                    and config.logging.mlflow.enable_span_comparison_traces
                ),
                trace_max_samples=config.logging.mlflow.max_traces_per_split,
            )
            evaluated_epochs.append(fallback_epoch)

            if mlflow_enabled:
                safe_log_metrics(
                    {f"dev_{k}": v for k, v in eval_result["metrics"].items()},
                    step=fallback_epoch,
                )
                safe_log_artifacts(
                    str(dev_dir), artifact_path=f"dev_epochs/epoch_{fallback_epoch:03d}"
                )

        best_model = SequenceTagger.load(model_for_test_path)
        test_eval = _evaluate_split(
            model=best_model,
            split_name="test",
            split_sentences=list(corpus.test),
            backend_mode=config.backend.mode,
            config=config,
            out_dir=paths["test_root"],
            epoch=None,
            trace_logging_enabled=(
                mlflow_enabled and config.logging.mlflow.enable_span_comparison_traces
            ),
            trace_max_samples=config.logging.mlflow.max_traces_per_split,
        )

        if mlflow_enabled:
            safe_log_metrics({f"test_{k}": v for k, v in test_eval["metrics"].items()})
            safe_log_artifact(str(model_for_test_path), artifact_path="model")
            safe_log_artifacts(str(paths["test_root"]), artifact_path="test_final")
            if paths["loss_tsv"].exists():
                safe_log_artifact(str(paths["loss_tsv"]), artifact_path="training")

            log_run_metadata(
                config,
                run_name=run_name,
                model_name=model_name,
                config_path=config_path,
                train_metrics_by_epoch=train_metrics_by_epoch,
            )

        manifest = _build_manifest(
            config=config,
            config_path=config_path,
            model_name=model_name,
            train_metrics_by_epoch=train_metrics_by_epoch,
            dev_epochs=evaluated_epochs,
        )
        write_json(paths["manifest"], manifest)
        if mlflow_enabled:
            safe_log_artifact(str(paths["manifest"]), artifact_path="data")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Flair NER finetuning experiment from YAML config."
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
