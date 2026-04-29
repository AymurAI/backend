from __future__ import annotations

from contextlib import contextmanager
import os
import sys
from pathlib import Path
from typing import Any, Iterator

from pydantic import BaseModel, ConfigDict

from aymurai.logger import get_logger

logger = get_logger(__name__)


def _prepare_mlflow_import_env() -> None:
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")


class MLflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    tracking_uri: str = "resources/outputs/mlruns"
    experiment_name: str = "aymurai-experiments"
    enable_generation_traces: bool = True
    request_timeout_s: float = 15.0
    request_max_retries: int = 2


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mlflow: MLflowConfig


def resolve_tracking_uri(value: str, *, project_root: Path) -> str:
    if "://" in value or value.startswith("databricks"):
        return value
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((project_root / path).resolve())


def configure_mlflow(config: MLflowConfig) -> tuple[bool, str | None]:
    if not config.enabled:
        return False, None

    timeout_s = max(1, int(round(float(config.request_timeout_s))))
    os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] = str(timeout_s)
    os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] = str(config.request_max_retries)

    try:
        _prepare_mlflow_import_env()
        import mlflow

        mlflow.set_tracking_uri(config.tracking_uri)
        mlflow.set_experiment(config.experiment_name)
        experiment = mlflow.get_experiment_by_name(config.experiment_name)
        return True, experiment.experiment_id if experiment else None
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "MLflow initialization failed; continuing without MLflow logging: %s",
            exc,
        )
        return False, None


def safe_log_artifact(local_path: str | Path, artifact_path: str | None = None) -> None:
    try:
        _prepare_mlflow_import_env()
        import mlflow

        mlflow.log_artifact(str(local_path), artifact_path=artifact_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Skipping MLflow artifact upload (%s -> %s): %s",
            local_path,
            artifact_path,
            exc,
        )


def safe_log_artifacts(local_dir: str | Path, artifact_path: str | None = None) -> None:
    try:
        _prepare_mlflow_import_env()
        import mlflow

        mlflow.log_artifacts(str(local_dir), artifact_path=artifact_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Skipping MLflow artifacts upload (%s -> %s): %s",
            local_dir,
            artifact_path,
            exc,
        )


def safe_log_metrics(metrics: dict[str, float]) -> None:
    try:
        _prepare_mlflow_import_env()
        import mlflow

        mlflow.log_metrics(metrics)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping MLflow metrics logging: %s", exc)


def safe_log_params(params: dict[str, object]) -> None:
    clean_params = {
        key: value
        for key, value in params.items()
        if value is None or isinstance(value, str | int | float | bool)
    }
    try:
        _prepare_mlflow_import_env()
        import mlflow

        mlflow.log_params(clean_params)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping MLflow params logging: %s", exc)


def safe_start_run(*, run_name: str, experiment_id: str | None = None) -> bool:
    try:
        _prepare_mlflow_import_env()
        import mlflow

        mlflow.start_run(run_name=run_name, experiment_id=experiment_id)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping MLflow run start: %s", exc)
        return False


def safe_set_tags(tags: dict[str, str]) -> None:
    try:
        _prepare_mlflow_import_env()
        import mlflow

        mlflow.set_tags(tags)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping MLflow tags logging: %s", exc)


def safe_end_run() -> None:
    try:
        _prepare_mlflow_import_env()
        import mlflow

        mlflow.end_run()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping MLflow run end: %s", exc)


@contextmanager
def safe_generation_trace_context(
    *,
    enabled: bool,
    name: str,
) -> Iterator[Any | None]:
    if not enabled:
        yield None
        return

    try:
        _prepare_mlflow_import_env()
        import mlflow

        if not hasattr(mlflow, "start_span"):
            yield None
            return

        span_context = mlflow.start_span(name=name, span_type="LLM")
        span = span_context.__enter__()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skipping MLflow generation trace start: %s", exc)
        yield None
        return

    try:
        yield span
    except BaseException:
        should_suppress = span_context.__exit__(*sys.exc_info())
        if not should_suppress:
            raise
    else:
        try:
            span_context.__exit__(None, None, None)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping MLflow generation trace end: %s", exc)


def safe_set_generation_trace_data(
    span: Any | None,
    *,
    sample_id: str,
    inputs: dict[str, object],
    outputs: dict[str, object],
    attributes: dict[str, object] | None = None,
    tags: dict[str, str] | None = None,
) -> None:
    if span is None:
        return

    try:
        _prepare_mlflow_import_env()
        import mlflow

        if tags and hasattr(mlflow, "update_current_trace"):
            try:
                mlflow.update_current_trace(tags=tags)
            except Exception:  # noqa: BLE001
                pass
        if hasattr(span, "set_inputs"):
            span.set_inputs(inputs)
        if hasattr(span, "set_outputs"):
            span.set_outputs(outputs)
        if hasattr(span, "set_attributes"):
            span.set_attributes(
                {
                    "sample_id": sample_id,
                    **(attributes or {}),
                }
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Skipping MLflow generation trace data logging for sample=%s: %s",
            sample_id,
            exc,
        )


def safe_log_generation_trace(
    *,
    enabled: bool,
    name: str,
    sample_id: str,
    inputs: dict[str, object],
    outputs: dict[str, object],
    attributes: dict[str, object] | None = None,
    tags: dict[str, str] | None = None,
) -> None:
    if not enabled:
        return

    with safe_generation_trace_context(enabled=enabled, name=name) as span:
        safe_set_generation_trace_data(
            span,
            sample_id=sample_id,
            inputs=inputs,
            outputs=outputs,
            attributes=attributes,
            tags=tags,
        )
