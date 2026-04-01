from __future__ import annotations

import csv
import html
import json
import os
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient
from pandas.errors import EmptyDataError, ParserError

from aymurai.experiments.ner_flair_finetunning.config import NERFinetuningConfig
from aymurai.logger import get_logger
from aymurai.utils.yaml_data import save_yaml

logger = get_logger(__name__)


def configure_mlflow(config: NERFinetuningConfig) -> tuple[bool, str | None]:
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
        return True, experiment_id
    except Exception as exc:
        logger.warning(
            "MLflow initialization failed; continuing without MLflow logging: %s", exc
        )
        return False, None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def write_comparisons_html(
    path: Path,
    *,
    split_name: str,
    comparisons: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fn_counter: Counter[str] = Counter()
    fp_counter: Counter[str] = Counter()
    sample_error_rows: list[tuple[str, int, int, int]] = []
    perfect_count = 0

    for row in comparisons:
        fn = row.get("false_negatives", [])
        fp = row.get("false_positives", [])
        if bool(row.get("perfect_span_set", False)):
            perfect_count += 1
        for span in fn:
            fn_counter[str(span.get("label", ""))] += 1
        for span in fp:
            fp_counter[str(span.get("label", ""))] += 1
        total_err = len(fn) + len(fp)
        sample_error_rows.append(
            (
                str(row.get("sample_id", "")),
                total_err,
                len(fn),
                len(fp),
            )
        )

    top_fn = fn_counter.most_common(10)
    top_fp = fp_counter.most_common(10)
    top_samples = sorted(sample_error_rows, key=lambda x: x[1], reverse=True)[:10]

    parts: list[str] = []
    parts.append(
        "<html><head><meta charset='utf-8'><style>"
        "body{font-family:Arial,Helvetica,sans-serif;margin:20px;}"
        "h1{margin:0 0 8px 0;} .meta{color:#555;margin-bottom:16px;}"
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;}"
        ".card{border:1px solid #ddd;border-radius:8px;padding:10px;background:#fff;}"
        "table{border-collapse:collapse;width:100%;font-size:12px;}"
        "th,td{border:1px solid #eee;padding:6px;text-align:left;}"
        "th{background:#f8f8f8;}"
        ".row{border:1px solid #ddd;border-radius:8px;padding:12px;margin-bottom:12px;}"
        ".ok{border-left:6px solid #2e7d32;} .ko{border-left:6px solid #c62828;}"
        ".txt{white-space:pre-wrap;background:#fafafa;border:1px solid #eee;padding:8px;border-radius:6px;}"
        ".badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;margin-right:6px;}"
        ".g{background:#e8f5e9;} .p{background:#e3f2fd;} .fn{background:#ffebee;} .fp{background:#fff3e0;}"
        "code{font-family:ui-monospace, Menlo, Monaco, Consolas, monospace;}"
        "</style></head><body>"
    )
    parts.append(f"<h1>Comparisons - {html.escape(split_name)}</h1>")
    parts.append(
        "<div class='meta'>"
        f"Samples: {len(comparisons)} | "
        f"Perfect span set: {perfect_count} ({(100.0 * perfect_count / max(1, len(comparisons))):.1f}%)"
        "</div>"
    )
    parts.append("<div class='grid'>")
    parts.append(
        "<div class='card'><h3>Top FN Labels</h3><table><tr><th>Label</th><th>Count</th></tr>"
    )
    for label, count in top_fn:
        parts.append(f"<tr><td>{html.escape(label)}</td><td>{int(count)}</td></tr>")
    if not top_fn:
        parts.append("<tr><td colspan='2'><em>No false negatives</em></td></tr>")
    parts.append("</table></div>")

    parts.append(
        "<div class='card'><h3>Top FP Labels</h3><table><tr><th>Label</th><th>Count</th></tr>"
    )
    for label, count in top_fp:
        parts.append(f"<tr><td>{html.escape(label)}</td><td>{int(count)}</td></tr>")
    if not top_fp:
        parts.append("<tr><td colspan='2'><em>No false positives</em></td></tr>")
    parts.append("</table></div>")
    parts.append("</div>")

    parts.append("<div class='card'><h3>Hardest Samples (Top 10)</h3>")
    parts.append(
        "<table><tr><th>Sample ID</th><th>Total Errors</th><th>FN</th><th>FP</th></tr>"
    )
    for sample_id, total_err, fn_n, fp_n in top_samples:
        parts.append(
            f"<tr><td>{html.escape(sample_id)}</td><td>{total_err}</td><td>{fn_n}</td><td>{fp_n}</td></tr>"
        )
    if not top_samples:
        parts.append("<tr><td colspan='4'><em>No samples</em></td></tr>")
    parts.append("</table></div>")

    for row in comparisons:
        perfect = bool(row.get("perfect_span_set", False))
        cls = "ok" if perfect else "ko"
        sample_id = html.escape(str(row.get("sample_id", "")))
        text = html.escape(str(row.get("text", "")))
        gold = row.get("gold_spans", [])
        pred = row.get("predicted_spans", [])
        fn = row.get("false_negatives", [])
        fp = row.get("false_positives", [])

        def _fmt(spans: list[dict[str, Any]]) -> str:
            if not spans:
                return "<em>None</em>"
            return "<br/>".join(
                html.escape(
                    f"[{s.get('label','')}] {s.get('text','')} ({s.get('start','')},{s.get('end','')})"
                )
                for s in spans
            )

        parts.append(f"<div class='row {cls}'>")
        parts.append(
            f"<div><strong>{sample_id}</strong> "
            f"<span class='badge g'>gold={len(gold)}</span>"
            f"<span class='badge p'>pred={len(pred)}</span>"
            f"<span class='badge fn'>fn={len(fn)}</span>"
            f"<span class='badge fp'>fp={len(fp)}</span>"
            "</div>"
        )
        parts.append(f"<div class='txt'>{text}</div>")
        parts.append(f"<div><strong>Gold spans</strong><br/>{_fmt(gold)}</div>")
        parts.append(f"<div><strong>Predicted spans</strong><br/>{_fmt(pred)}</div>")
        if fn:
            parts.append(f"<div><strong>False negatives</strong><br/>{_fmt(fn)}</div>")
        if fp:
            parts.append(f"<div><strong>False positives</strong><br/>{_fmt(fp)}</div>")
        parts.append("</div>")

    parts.append("</body></html>")
    path.write_text("".join(parts), encoding="utf-8")


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    upper_to_original = {col.upper(): col for col in columns}
    for candidate in candidates:
        col = upper_to_original.get(candidate.upper())
        if col:
            return col
    return None


def _extract_epoch_metrics(df: pd.DataFrame) -> dict[int, dict[str, float]]:
    if df.empty:
        return {}

    columns = list(df.columns)
    epoch_col = _find_column(columns, ["EPOCH"])
    train_loss_col = _find_column(columns, ["TRAIN_LOSS", "LOSS"])
    dev_loss_col = _find_column(columns, ["DEV_LOSS", "VAL_LOSS"])
    dev_f1_col = _find_column(columns, ["DEV_F1", "VAL_F1"])
    lr_col = _find_column(columns, ["LEARNING_RATE", "LR"])

    if not epoch_col:
        return {}

    metrics_by_epoch: dict[int, dict[str, float]] = {}
    for _, row in df.iterrows():
        raw_epoch = row[epoch_col]
        try:
            epoch = int(raw_epoch)
        except (TypeError, ValueError):
            # Some transient writes may include a repeated header-like row.
            continue
        metrics: dict[str, float] = {}

        if train_loss_col is not None and pd.notna(row[train_loss_col]):
            metrics["train_loss"] = float(row[train_loss_col])
        if dev_loss_col is not None and pd.notna(row[dev_loss_col]):
            metrics["dev_loss"] = float(row[dev_loss_col])
        if dev_f1_col is not None and pd.notna(row[dev_f1_col]):
            metrics["dev_f1"] = float(row[dev_f1_col])
        if lr_col is not None and pd.notna(row[lr_col]):
            metrics["learning_rate"] = float(row[lr_col])

        metrics_by_epoch[epoch] = metrics
    return metrics_by_epoch


def start_live_training_logging(
    output_dir: Path,
    *,
    enabled: bool,
    run_id: str | None = None,
    poll_interval_s: float = 8.0,
) -> tuple[threading.Event | None, threading.Thread | None]:
    if not enabled:
        return None, None

    loss_file = output_dir / "loss.tsv"
    stop_event = threading.Event()
    client = MlflowClient()

    def _worker() -> None:
        seen_epochs: set[int] = set()
        while not stop_event.is_set():
            try:
                if loss_file.exists():
                    df = pd.read_csv(loss_file, sep="\t")
                    for epoch, metrics in sorted(_extract_epoch_metrics(df).items()):
                        if epoch in seen_epochs or not metrics:
                            continue
                        if run_id:
                            for key, value in metrics.items():
                                client.log_metric(
                                    run_id=run_id,
                                    key=key,
                                    value=float(value),
                                    step=int(epoch),
                                )
                        else:
                            mlflow.log_metrics(metrics, step=epoch)
                        seen_epochs.add(epoch)
            except (EmptyDataError, ParserError):
                # Flair may create/update loss.tsv while it's still empty or partially written.
                pass
            except Exception as exc:
                logger.warning(
                    "Live MLflow epoch logging skipped in this poll: %s", exc
                )
            stop_event.wait(max(1.0, float(poll_interval_s)))

        try:
            if loss_file.exists():
                df = pd.read_csv(loss_file, sep="\t")
                for epoch, metrics in sorted(_extract_epoch_metrics(df).items()):
                    if epoch in seen_epochs or not metrics:
                        continue
                    if run_id:
                        for key, value in metrics.items():
                            client.log_metric(
                                run_id=run_id,
                                key=key,
                                value=float(value),
                                step=int(epoch),
                            )
                    else:
                        mlflow.log_metrics(metrics, step=epoch)
                    seen_epochs.add(epoch)
        except (EmptyDataError, ParserError):
            pass
        except Exception as exc:
            logger.warning("Final live MLflow epoch flush failed: %s", exc)

    thread = threading.Thread(
        target=_worker,
        name="mlflow-live-training-logger",
        daemon=True,
    )
    thread.start()
    return stop_event, thread


def log_training_curves_from_tsv(
    output_dir: Path, *, enabled: bool
) -> dict[int, dict[str, float]]:
    loss_file = output_dir / "loss.tsv"
    if not loss_file.exists():
        logger.warning("Flair loss.tsv not found at %s", loss_file)
        return {}

    df = pd.read_csv(loss_file, sep="\t")
    if df.empty:
        return {}

    metrics_by_epoch = _extract_epoch_metrics(df)
    if not metrics_by_epoch:
        logger.warning("Could not parse epoch column in %s", loss_file)
        return {}

    for epoch, metrics in sorted(metrics_by_epoch.items()):
        if enabled and metrics:
            mlflow.log_metrics(metrics, step=epoch)

    return metrics_by_epoch


def log_run_metadata(
    config: NERFinetuningConfig,
    *,
    run_name: str,
    model_name: str,
    config_path: str,
    train_metrics_by_epoch: dict[int, dict[str, float]],
) -> None:
    params = {
        "run_name": run_name,
        "experiment_name": config.experiment.name,
        "backend_mode": config.backend.mode,
        "model": model_name,
        "dataset_path": config.data.input_path,
        "learning_rate": config.training.learning_rate,
        "mini_batch_size": config.training.mini_batch_size,
        "max_epochs": config.training.max_epochs,
        "dev_eval_start_epoch": config.training.dev_eval_start_epoch,
        "dev_eval_every_k_epochs": config.training.dev_eval_every_k_epochs,
        "test_eval_epoch": (
            ""
            if config.training.test_eval_epoch is None
            else config.training.test_eval_epoch
        ),
        "include_token_relaxed": config.metrics.include_token_relaxed,
    }
    mlflow.log_params(params)

    if train_metrics_by_epoch:
        last_epoch = max(train_metrics_by_epoch)
        last_metrics = train_metrics_by_epoch[last_epoch]
        if last_metrics:
            mlflow.log_metrics({f"final_train_{k}": v for k, v in last_metrics.items()})

    with tempfile.TemporaryDirectory() as temp_dir:
        tmp = Path(temp_dir)
        config_out = tmp / "config.yaml"
        save_yaml(config.model_dump(mode="json"), str(config_out))

        marker = tmp / "run_context.json"
        marker.write_text(
            json.dumps({"config_path": config_path, "run_name": run_name}, indent=2),
            encoding="utf-8",
        )

        safe_log_artifact(str(config_out), artifact_path="config")
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


def safe_log_metrics(metrics: dict[str, float], *, step: int | None = None) -> None:
    try:
        if step is None:
            mlflow.log_metrics(metrics)
        else:
            mlflow.log_metrics(metrics, step=step)
    except Exception as exc:
        logger.warning("Skipping MLflow metrics logging (step=%s): %s", step, exc)


def log_span_comparison_trace(
    *,
    enabled: bool,
    split_name: str,
    sample_id: str,
    epoch: int | None,
    text: str,
    gold_spans: list[dict[str, Any]],
    predicted_spans: list[dict[str, Any]],
    false_negatives: list[dict[str, Any]],
    false_positives: list[dict[str, Any]],
    perfect_span_set: bool,
) -> None:
    if not enabled:
        return

    if not hasattr(mlflow, "start_span"):
        return

    try:
        with mlflow.start_span(name=f"ner_{split_name}_span_comparison") as span:
            # Guarded because tracing API surfaces may vary by mlflow version.
            if hasattr(span, "set_inputs"):
                span.set_inputs(
                    {
                        "sample_id": sample_id,
                        "split": split_name,
                        "epoch": epoch,
                        "text": text,
                    }
                )
            if hasattr(span, "set_outputs"):
                span.set_outputs(
                    {
                        "perfect_span_set": perfect_span_set,
                        "gold_spans": gold_spans,
                        "predicted_spans": predicted_spans,
                        "false_negatives": false_negatives,
                        "false_positives": false_positives,
                    }
                )
            if hasattr(span, "set_attributes"):
                span.set_attributes(
                    {
                        "sample_id": sample_id,
                        "split": split_name,
                        "epoch": -1 if epoch is None else int(epoch),
                        "perfect_span_set": bool(perfect_span_set),
                        "gold_spans_count": len(gold_spans),
                        "predicted_spans_count": len(predicted_spans),
                        "false_negatives_count": len(false_negatives),
                        "false_positives_count": len(false_positives),
                    }
                )
    except Exception as exc:
        logger.warning(
            "Skipping MLflow trace logging for sample=%s split=%s: %s",
            sample_id,
            split_name,
            exc,
        )
