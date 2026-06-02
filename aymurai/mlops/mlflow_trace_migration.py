from __future__ import annotations

import argparse
import json
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aymurai.logger.logger import get_logger

logger = get_logger(__name__)

MANIFEST_FILENAME = "manifest.json"
TRACES_FILENAME = "traces.jsonl"


class TraceMigrationError(RuntimeError):
    """Raised when MLflow trace migration cannot proceed."""


def _import_mlflow() -> tuple[Any, Any]:
    try:
        import mlflow
        from mlflow import MlflowClient
    except ImportError as exc:
        raise TraceMigrationError(
            "MLflow is required for trace migration. Install the project with the "
            "`mlops` dependency group or otherwise make `mlflow` available."
        ) from exc
    return mlflow, MlflowClient


def _configure_tracking_uri(mlflow: Any, tracking_uri: str | None) -> str | None:
    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)
        return tracking_uri
    return mlflow.get_tracking_uri()


def _build_client(MlflowClient: Any, tracking_uri: str | None) -> Any:
    return MlflowClient(tracking_uri=tracking_uri) if tracking_uri else MlflowClient()


def _trace_id(trace: Any) -> str:
    info = getattr(trace, "info", None)
    if info is not None:
        return getattr(info, "trace_id", None) or getattr(info, "request_id", None)
    return getattr(trace, "trace_id", None) or getattr(trace, "request_id", None)


def _started_trace_ids(trace: Any) -> tuple[str, str]:
    info = getattr(trace, "info", None)
    trace_identifier = (
        getattr(trace, "trace_id", None)
        or getattr(info, "trace_id", None)
        or getattr(trace, "request_id", None)
        or getattr(info, "request_id", None)
    )
    span_identifier = getattr(trace, "span_id", None) or getattr(info, "span_id", None)
    if not trace_identifier or not span_identifier:
        raise TraceMigrationError(
            f"Could not determine destination trace/span identifiers from {trace!r}"
        )
    return trace_identifier, span_identifier


def _started_span_id(span: Any) -> str:
    info = getattr(span, "info", None)
    span_identifier = getattr(span, "span_id", None) or getattr(info, "span_id", None)
    if not span_identifier:
        raise TraceMigrationError(
            f"Could not determine destination span identifier from {span!r}"
        )
    return span_identifier


def _get_trace_metadata(
    trace_dict: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    info = trace_dict.get("info", {})
    return info.get("trace_metadata", {}) or {}, info.get("tags", {}) or {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _search_traces_for_run(client: Any, experiment_id: str, run_id: str) -> list[Any]:
    traces: list[Any] = []
    page_token: str | None = None

    while True:
        page = client.search_traces(
            locations=[experiment_id],
            run_id=run_id,
            max_results=200,
            page_token=page_token,
        )
        traces.extend(page)
        page_token = getattr(page, "token", None)
        if not page_token:
            return traces


def export_run_traces(
    *,
    run_id: str,
    output_dir: str,
    tracking_uri: str | None = None,
) -> Path:
    mlflow, MlflowClient = _import_mlflow()
    resolved_tracking_uri = _configure_tracking_uri(mlflow, tracking_uri)
    client = _build_client(MlflowClient, resolved_tracking_uri)

    run = client.get_run(run_id)
    experiment_id = run.info.experiment_id
    traces = _search_traces_for_run(client, experiment_id, run_id)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    serialized_traces = []
    for trace in traces:
        trace_identifier = _trace_id(trace)
        full_trace = client.get_trace(trace_identifier)
        serialized_traces.append(full_trace.to_dict())

    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "tracking_uri": resolved_tracking_uri,
        "run_id": run_id,
        "experiment_id": experiment_id,
        "trace_count": len(serialized_traces),
    }

    _write_json(output_path / MANIFEST_FILENAME, manifest)
    _write_jsonl(output_path / TRACES_FILENAME, serialized_traces)
    logger.info(
        "Exported %s trace(s) for run %s into %s",
        len(serialized_traces),
        run_id,
        output_path,
    )
    return output_path


def _span_dicts(trace_dict: dict[str, Any]) -> list[dict[str, Any]]:
    return trace_dict.get("data", {}).get("spans", []) or []


def _span_id(span: dict[str, Any]) -> str:
    span_id = span.get("span_id")
    if not span_id:
        raise TraceMigrationError(f"Malformed span payload without span_id: {span}")
    return span_id


def _span_parent_id(span: dict[str, Any]) -> str | None:
    return span.get("parent_id")


def _span_name(span: dict[str, Any]) -> str:
    return span.get("name") or "unnamed-span"


def _span_status(span: dict[str, Any]) -> str:
    status = span.get("status")
    if isinstance(status, dict):
        return status.get("status_code") or status.get("statusCode") or "OK"
    if isinstance(status, str):
        return status
    return "OK"


def _span_attributes(span: dict[str, Any]) -> dict[str, Any]:
    return span.get("attributes", {}) or {}


def _span_inputs(span: dict[str, Any]) -> Any:
    return span.get("inputs")


def _span_outputs(span: dict[str, Any]) -> Any:
    return span.get("outputs")


def _span_start_time_ns(span: dict[str, Any]) -> int | None:
    return span.get("start_time_ns")


def _span_end_time_ns(span: dict[str, Any]) -> int | None:
    return span.get("end_time_ns")


def _span_type(span: dict[str, Any]) -> str:
    return span.get("span_type") or "UNKNOWN"


def _sorted_spans_for_replay(
    spans: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    root_candidates = [span for span in spans if not _span_parent_id(span)]
    if len(root_candidates) != 1:
        raise TraceMigrationError(
            f"Expected exactly one root span, found {len(root_candidates)}"
        )

    root = root_candidates[0]
    by_id = {_span_id(span): span for span in spans}
    depth_cache: dict[str, int] = {}

    def depth(span: dict[str, Any]) -> int:
        span_identifier = _span_id(span)
        if span_identifier in depth_cache:
            return depth_cache[span_identifier]
        parent_identifier = _span_parent_id(span)
        if not parent_identifier:
            depth_cache[span_identifier] = 0
            return 0
        if parent_identifier not in by_id:
            raise TraceMigrationError(
                f"Span {_span_id(span)} references missing parent {parent_identifier}"
            )
        depth_cache[span_identifier] = depth(by_id[parent_identifier]) + 1
        return depth_cache[span_identifier]

    children = [span for span in spans if _span_id(span) != _span_id(root)]
    for span in children:
        depth(span)

    children.sort(
        key=lambda span: (
            depth_cache[_span_id(span)],
            _span_start_time_ns(span) or 0,
        )
    )
    return root, children, depth_cache


def _replay_assessments(
    *,
    mlflow: Any,
    trace_dict: dict[str, Any],
    destination_trace_id: str,
    source_to_destination_span_ids: dict[str, str],
) -> int:
    try:
        from mlflow.entities.assessment import Assessment
    except Exception:
        logger.warning(
            "MLflow Assessment APIs unavailable; skipping trace assessments."
        )
        return 0

    count = 0
    assessments = trace_dict.get("info", {}).get("assessments", []) or []
    for assessment_payload in assessments:
        if assessment_payload.get("valid") is False:
            continue
        if assessment_payload.get("overrides"):
            logger.warning(
                "Skipping overridden assessment %s on trace %s; override history is not preserved.",
                assessment_payload.get("assessment_id")
                or assessment_payload.get("assessmentId"),
                trace_dict.get("info", {}).get("trace_id"),
            )
            continue

        payload = dict(assessment_payload)
        payload.pop("assessment_id", None)
        payload.pop("assessmentId", None)
        source_span_id = payload.get("span_id")
        if source_span_id:
            payload["span_id"] = source_to_destination_span_ids.get(source_span_id)

        try:
            assessment = Assessment.from_dictionary(payload)
            mlflow.log_assessment(trace_id=destination_trace_id, assessment=assessment)
            count += 1
        except Exception as exc:
            logger.warning(
                "Skipping assessment %s on trace %s: %s",
                assessment_payload.get("name"),
                trace_dict.get("info", {}).get("trace_id"),
                exc,
            )
    return count


def _replay_trace(
    *,
    mlflow: Any,
    client: Any,
    destination_run_id: str,
    destination_experiment_id: str,
    trace_dict: dict[str, Any],
) -> tuple[str, int]:
    spans = _span_dicts(trace_dict)
    if not spans:
        raise TraceMigrationError("Trace payload does not contain any spans.")

    root, children, depth_cache = _sorted_spans_for_replay(spans)
    trace_metadata, trace_tags = _get_trace_metadata(trace_dict)
    span_id_map: dict[str, str] = {}

    tracing_context = (
        mlflow.tracing.context(metadata=trace_metadata, tags=trace_tags)
        if hasattr(mlflow, "tracing") and hasattr(mlflow.tracing, "context")
        else nullcontext()
    )

    with mlflow.start_run(run_id=destination_run_id):
        with tracing_context:
            destination_root = client.start_trace(
                name=_span_name(root),
                span_type=_span_type(root),
                inputs=_span_inputs(root),
                attributes=_span_attributes(root),
                tags=trace_tags,
                experiment_id=destination_experiment_id,
                start_time_ns=_span_start_time_ns(root),
            )
            destination_trace_id, destination_root_span_id = _started_trace_ids(
                destination_root
            )
            span_id_map[_span_id(root)] = destination_root_span_id

            pending = list(children)
            while pending:
                progressed = False
                for span in list(pending):
                    parent_identifier = _span_parent_id(span)
                    if parent_identifier not in span_id_map:
                        continue
                    destination_span = client.start_span(
                        name=_span_name(span),
                        trace_id=destination_trace_id,
                        parent_id=span_id_map[parent_identifier],
                        span_type=_span_type(span),
                        inputs=_span_inputs(span),
                        attributes=_span_attributes(span),
                        start_time_ns=_span_start_time_ns(span),
                    )
                    span_id_map[_span_id(span)] = _started_span_id(destination_span)
                    pending.remove(span)
                    progressed = True
                if not progressed:
                    unresolved = [_span_id(span) for span in pending]
                    raise TraceMigrationError(
                        f"Could not resolve parent chain for spans: {unresolved}"
                    )

            children_to_end = sorted(
                children,
                key=lambda span: (
                    depth_cache[_span_id(span)],
                    _span_end_time_ns(span) or 0,
                ),
                reverse=True,
            )
            for span in children_to_end:
                client.end_span(
                    trace_id=destination_trace_id,
                    span_id=span_id_map[_span_id(span)],
                    outputs=_span_outputs(span),
                    attributes=_span_attributes(span),
                    status=_span_status(span),
                    end_time_ns=_span_end_time_ns(span),
                )

            client.end_trace(
                trace_id=destination_trace_id,
                outputs=_span_outputs(root),
                attributes=_span_attributes(root),
                status=_span_status(root),
                end_time_ns=_span_end_time_ns(root),
            )

    assessments_replayed = _replay_assessments(
        mlflow=mlflow,
        trace_dict=trace_dict,
        destination_trace_id=destination_trace_id,
        source_to_destination_span_ids=span_id_map,
    )
    return destination_trace_id, assessments_replayed


def import_run_traces(
    *,
    input_dir: str,
    destination_run_id: str,
    tracking_uri: str | None = None,
) -> dict[str, Any]:
    mlflow, MlflowClient = _import_mlflow()
    resolved_tracking_uri = _configure_tracking_uri(mlflow, tracking_uri)
    client = _build_client(MlflowClient, resolved_tracking_uri)

    destination_run = client.get_run(destination_run_id)
    destination_experiment_id = destination_run.info.experiment_id

    input_path = Path(input_dir)
    manifest_path = input_path / MANIFEST_FILENAME
    traces_path = input_path / TRACES_FILENAME
    if not traces_path.exists():
        raise TraceMigrationError(f"Missing trace payload file: {traces_path}")

    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    trace_dicts = _read_jsonl(traces_path)
    imported_trace_ids: list[str] = []
    assessments_replayed = 0

    for trace_dict in trace_dicts:
        trace_id, replayed = _replay_trace(
            mlflow=mlflow,
            client=client,
            destination_run_id=destination_run_id,
            destination_experiment_id=destination_experiment_id,
            trace_dict=trace_dict,
        )
        imported_trace_ids.append(trace_id)
        assessments_replayed += replayed

    result = {
        "source_run_id": manifest.get("run_id"),
        "destination_run_id": destination_run_id,
        "destination_experiment_id": destination_experiment_id,
        "imported_trace_count": len(imported_trace_ids),
        "imported_trace_ids": imported_trace_ids,
        "replayed_assessment_count": assessments_replayed,
    }
    logger.info(
        "Imported %s trace(s) into run %s and replayed %s assessment(s).",
        len(imported_trace_ids),
        destination_run_id,
        assessments_replayed,
    )
    return result


def _build_export_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export MLflow traces associated with a given run into manifest.json plus traces.jsonl."
    )
    parser.add_argument("--run-id", required=True, help="Source MLflow run ID.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where manifest.json and traces.jsonl will be written.",
    )
    parser.add_argument(
        "--tracking-uri",
        default=None,
        help="Source MLflow tracking URI. Defaults to MLFLOW_TRACKING_URI/current MLflow configuration.",
    )
    return parser


def _build_import_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import exported MLflow traces into an existing destination run."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing manifest.json and traces.jsonl from the export command.",
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="Destination MLflow run ID that should own the replayed traces.",
    )
    parser.add_argument(
        "--tracking-uri",
        default=None,
        help="Destination MLflow tracking URI. Defaults to MLFLOW_TRACKING_URI/current MLflow configuration.",
    )
    return parser


def main_export() -> None:
    args = _build_export_parser().parse_args()
    export_run_traces(
        run_id=args.run_id,
        output_dir=args.output_dir,
        tracking_uri=args.tracking_uri,
    )


def main_import() -> None:
    args = _build_import_parser().parse_args()
    import_run_traces(
        input_dir=args.input_dir,
        destination_run_id=args.run_id,
        tracking_uri=args.tracking_uri,
    )


if __name__ == "__main__":
    main_export()
