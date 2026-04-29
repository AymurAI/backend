from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import time
import unicodedata
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow
import requests
from tqdm import tqdm

from aymurai.experiments.ner_langextract_alignment.clients import (
    call_anonymizer_predict,
    call_extraction_api,
    discover_documents,
    load_paragraphs_jsonl,
)
from aymurai.experiments.ner_langextract_alignment.compare import compare_entities
from aymurai.experiments.ner_langextract_alignment.config import (
    NERLangExtractRunConfig,
    load_experiment_config,
    render_run_name,
)
from aymurai.experiments.ner_langextract_alignment.labelstudio_export import (
    export_labelstudio_tasks,
)
from aymurai.experiments.ner_langextract_alignment.labelstudio_import import (
    consolidate_datasets,
    load_labelstudio_tasks,
    parse_labelstudio_decisions,
)
from aymurai.experiments.ner_langextract_alignment.langextract_runner import (
    build_tracing_model,
    load_examples_from_yaml,
    run_langextract,
)
from aymurai.experiments.ner_langextract_alignment.manifest import (
    build_documents_manifest,
    build_paragraph_manifest,
    sha256_file,
)
from aymurai.experiments.ner_langextract_alignment.mlflow_logging import (
    configure_mlflow,
    log_run_metadata,
    safe_log_artifact,
    safe_log_artifacts,
    serialize_traces_for_logging,
    summarize_metrics,
    write_jsonl,
    write_traces_summary_csv,
)
from aymurai.experiments.ner_langextract_alignment.normalize import (
    parse_langextract_predictions,
    parse_ner_predictions,
    serialize_entity,
)
from aymurai.experiments.ner_langextract_alignment.types import LLMTrace
from aymurai.experiments.ner_holdout_evaluation.loaders import load_conll_bio
from aymurai.logger import get_logger
from aymurai.settings import load_env
from aymurai.utils.yaml_data import load_yaml

load_env()

logger = get_logger(__name__)

TAG_RE = re.compile(r"(?is)<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\\1>")
BREAK_TAG_RE = re.compile(r"(?is)<\\s*(br|/p|/div|/li|/tr)\\s*/?>")


def _clean_hf_text(text: str, *, collapse_lines: bool = False) -> str:
    value = str(text or "")
    value = html.unescape(value)
    value = SCRIPT_STYLE_RE.sub(" ", value)
    value = BREAK_TAG_RE.sub("\n", value)
    value = TAG_RE.sub(" ", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")

    value = "".join(
        ch
        for ch in value
        if ch in {"\n", "\t", " "} or not unicodedata.category(ch).startswith("C")
    )

    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r"\n{2,}", "\n", value)
    value = "\n".join(line.strip() for line in value.split("\n"))
    value = "\n".join(line for line in value.split("\n") if line)
    value = value.strip()

    if collapse_lines:
        value = re.sub(r"\s+", " ", value).strip()
    return value


def _resolve_hf_cache_dir(config: NERLangExtractRunConfig) -> str:
    if config.data.input_hf_cache_dir:
        cache_dir = Path(config.data.input_hf_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return str(cache_dir)

    configured = os.getenv("HF_DATASETS_CACHE") or os.getenv("HF_HOME")
    if configured:
        configured_path = Path(configured)
        try:
            configured_path.mkdir(parents=True, exist_ok=True)
            test_file = configured_path / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
            return str(configured_path)
        except OSError:
            logger.warning(
                "HF cache path is not writable (%s). Falling back to local .cache/huggingface.",
                configured_path,
            )

    fallback = Path(".cache/huggingface")
    fallback.mkdir(parents=True, exist_ok=True)
    return str(fallback)


def _configure_hf_cache_env(cache_dir: str) -> None:
    """
    Ensure both `datasets` and `huggingface_hub` write to a writable cache root.
    """
    root = Path(cache_dir)
    datasets_cache = root / "datasets"
    hub_cache = root / "hub"
    assets_cache = root / "assets"
    xet_cache = root / "xet"

    datasets_cache.mkdir(parents=True, exist_ok=True)
    hub_cache.mkdir(parents=True, exist_ok=True)
    assets_cache.mkdir(parents=True, exist_ok=True)
    xet_cache.mkdir(parents=True, exist_ok=True)

    os.environ["HF_HOME"] = str(root)
    os.environ["HF_DATASETS_CACHE"] = str(datasets_cache)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hub_cache)
    os.environ["HF_ASSETS_CACHE"] = str(assets_cache)
    os.environ["HF_XET_CACHE"] = str(xet_cache)


def _ensure_dirs(config: NERLangExtractRunConfig, run_name: str) -> dict[str, Path]:
    base = Path(config.outputs.base_dir) / run_name
    base.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {
        "base": base,
        "reports": base / "reports",
        "raw": base / "predictions_raw",
        "comparisons": base / "comparisons",
        "samples": base / config.outputs.samples_jsonl,
        "traces_jsonl": base / config.outputs.traces_jsonl,
        "traces_csv": base / config.outputs.traces_summary_csv,
        "train_candidates": base / config.outputs.train_candidates_jsonl,
        "review_required": base / config.outputs.review_required_jsonl,
    }

    for key in ["reports", "raw", "comparisons"]:
        paths[key].mkdir(parents=True, exist_ok=True)

    if config.labelstudio.enabled and config.labelstudio.export_dir:
        labelstudio_root = Path(config.labelstudio.export_dir)
        outputs_root = Path(config.outputs.base_dir)

        if labelstudio_root.resolve() == outputs_root.resolve():
            # Keep Label Studio exports grouped under each run directory.
            paths["labelstudio"] = base / "labelstudio"
        else:
            paths["labelstudio"] = labelstudio_root / run_name
        paths["labelstudio"].mkdir(parents=True, exist_ok=True)

    return paths


def _load_mapping(path: str) -> dict[str, str]:
    payload = load_yaml(path)
    mapping = payload.get("labels", payload) if isinstance(payload, dict) else {}
    return {str(k).strip().upper(): str(v).strip().upper() for k, v in mapping.items()}


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text_dedupe_key(text: str) -> str:
    # Normalize repeated whitespace so semantically identical paragraphs collapse.
    return " ".join((text or "").split())


def _deduplicate_samples_by_text(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique_samples: list[dict[str, Any]] = []
    duplicated_count = 0

    for sample in samples:
        key = _text_dedupe_key(str(sample.get("text") or ""))
        if key in seen:
            duplicated_count += 1
            continue
        seen.add(key)
        unique_samples.append(sample)

    if duplicated_count:
        logger.info(
            "deduplicate_by_text enabled: removed %s duplicated samples (kept %s)",
            duplicated_count,
            len(unique_samples),
        )
    return unique_samples


def _record_from_paragraph(
    *,
    sample_id: str,
    document_id: str,
    paragraph_id: str,
    source_path: str | None,
    text: str,
    ner_payload: dict[str, Any],
    langextract_payload: dict[str, Any],
    ner_latency_ms: float,
    lx_latency_ms: float,
    mapping: dict[str, str],
    config: NERLangExtractRunConfig,
) -> dict[str, Any]:
    ner_entities, ner_flags = parse_ner_predictions(
        text=text,
        labels=ner_payload.get("labels", []),
        normalize_case=config.comparison.normalize_case,
        normalize_accents=config.comparison.normalize_accents,
        normalize_punctuation=config.comparison.normalize_punctuation,
    )
    lx_entities, lx_flags = parse_langextract_predictions(
        text=text,
        extractions=langextract_payload.get("extractions", []),
        label_mapping=mapping,
        normalize_case=config.comparison.normalize_case,
        normalize_accents=config.comparison.normalize_accents,
        normalize_punctuation=config.comparison.normalize_punctuation,
    )
    if langextract_payload.get("error"):
        lx_flags.append("langextract_inference_error")

    comparison = compare_entities(ner_entities, lx_entities)

    return {
        "sample_id": sample_id,
        "document_id": document_id,
        "paragraph_id": paragraph_id,
        "source_path": source_path,
        "text": text,
        "ner_predictions": [serialize_entity(ent) for ent in ner_entities],
        "langextract_predictions": [serialize_entity(ent) for ent in lx_entities],
        "comparison": {
            "status": comparison.status,
            "exact_match": [serialize_entity(ent) for ent in comparison.exact_match],
            "partial_match": [
                serialize_entity(ent) for ent in comparison.partial_match
            ],
            "only_in_ner": [serialize_entity(ent) for ent in comparison.only_in_ner],
            "only_in_langextract": [
                serialize_entity(ent) for ent in comparison.only_in_langextract
            ],
        },
        "quality_flags": sorted(set(ner_flags + lx_flags)),
        "timestamps": {"processed_at": _timestamp_now()},
        "latency_ms": {
            "ner": float(ner_latency_ms),
            "langextract": float(lx_latency_ms),
        },
    }


def _load_input_paragraphs(config: NERLangExtractRunConfig) -> list[dict[str, Any]]:
    if not config.data.input_paragraphs_jsonl:
        return []

    rows = load_paragraphs_jsonl(Path(config.data.input_paragraphs_jsonl))
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        out.append(
            {
                "sample_id": str(row.get("sample_id") or f"sample-{idx}"),
                "document_id": str(row.get("document_id") or "external"),
                "paragraph_id": str(row.get("paragraph_id") or str(idx)),
                "source_path": row.get("source_path"),
                "text": str(row.get("text") or ""),
            }
        )

    if config.data.max_paragraphs is not None:
        out = out[: config.data.max_paragraphs]

    return out


def _load_input_bio_txt(config: NERLangExtractRunConfig) -> list[dict[str, Any]]:
    if not config.data.input_bio_txt:
        return []

    source_path = Path(config.data.input_bio_txt)
    samples = load_conll_bio(source_path)
    out: list[dict[str, Any]] = []
    for idx, sample in enumerate(samples):
        out.append(
            {
                "sample_id": str(sample.sample_id or f"bio-{idx}"),
                "document_id": "bio_txt",
                "paragraph_id": str(idx),
                "source_path": str(source_path),
                "text": str(sample.text or ""),
            }
        )

    if config.data.max_paragraphs is not None:
        out = out[: config.data.max_paragraphs]

    return out


def _load_input_hf_dataset(config: NERLangExtractRunConfig) -> list[dict[str, Any]]:
    dataset_name = config.data.input_hf_dataset
    if not dataset_name:
        return []

    cache_dir = _resolve_hf_cache_dir(config)
    _configure_hf_cache_env(cache_dir)

    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise ImportError(
            "Hugging Face datasets support requires the `datasets` package."
        ) from exc

    ds = load_dataset(
        dataset_name,
        name=config.data.input_hf_config_name,
        split=config.data.input_hf_split,
        cache_dir=cache_dir,
    )

    language_column = config.data.input_hf_language_column
    language_value = config.data.input_hf_language_value
    text_column = config.data.input_hf_text_column
    sample_id_column = config.data.input_hf_sample_id_column
    document_id_column = config.data.input_hf_document_id_column

    if language_column and language_value is not None:
        ds = ds.filter(lambda row: row.get(language_column) == language_value)

    out: list[dict[str, Any]] = []
    for idx, row in enumerate(ds):
        text = str(row.get(text_column) or "")
        if config.data.input_hf_clean_text:
            text = _clean_hf_text(
                text,
                collapse_lines=config.data.input_hf_cleaning_mode == "collapse_lines",
            )
        out.append(
            {
                "sample_id": str(
                    row.get(sample_id_column)
                    if sample_id_column
                    else f"hf-{config.data.input_hf_split}-{idx}"
                ),
                "document_id": str(
                    row.get(document_id_column) if document_id_column else dataset_name
                ),
                "paragraph_id": str(idx),
                "source_path": f"hf://{dataset_name}/{config.data.input_hf_split}",
                "text": text,
            }
        )

    if config.data.max_paragraphs is not None:
        out = out[: config.data.max_paragraphs]

    return out


def _extract_paragraphs_from_docs(
    *,
    config: NERLangExtractRunConfig,
    session: requests.Session,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    docs_root = Path(config.data.input_documents_dir or "")
    documents = discover_documents(docs_root, config.data.include_extensions)

    if config.data.max_documents is not None:
        documents = documents[: config.data.max_documents]

    manifest = build_documents_manifest(documents)
    samples: list[dict[str, Any]] = []

    for doc_path in tqdm(documents, desc="extract-documents"):
        logger.info("document-extract start: path=%s", doc_path)
        extraction_response = call_extraction_api(
            session,
            base_url=config.api.base_url,
            path=config.api.document_extract_path,
            file_path=doc_path,
            use_cache=config.api.use_cache,
            timeout_s=config.api.timeout_s,
            retries=config.api.retries,
            retry_backoff_s=config.api.retry_backoff_s,
        )

        if extraction_response.get("status") != "success":
            logger.warning(
                "document extraction failed: path=%s detail=%s",
                doc_path,
                extraction_response.get("detail"),
            )
            continue

        detail = extraction_response.get("detail") or {}
        document_id = str(detail.get("document_id") or doc_path.stem)
        paragraphs = detail.get("document", []) or []
        logger.info(
            "document-extract done: path=%s document_id=%s paragraphs=%s elapsed_ms=%s",
            doc_path,
            document_id,
            len(paragraphs),
            extraction_response.get("elapsed_ms"),
        )
        if not paragraphs:
            logger.warning("document produced 0 paragraphs: path=%s", doc_path)

        for idx, text in enumerate(paragraphs):
            samples.append(
                {
                    "sample_id": f"{document_id}-{idx}",
                    "document_id": document_id,
                    "paragraph_id": str(idx),
                    "source_path": str(doc_path),
                    "text": str(text),
                }
            )

    if config.data.max_paragraphs is not None:
        samples = samples[: config.data.max_paragraphs]

    return samples, manifest


def _write_reports(samples: list[dict[str, Any]], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)

    status_counts: dict[str, int] = {}
    label_discrepancies: dict[str, int] = {}

    for sample in samples:
        status = sample.get("comparison", {}).get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

        for ent in sample.get("comparison", {}).get("only_in_ner", []):
            lbl = ent.get("label", "")
            label_discrepancies[lbl] = label_discrepancies.get(lbl, 0) + 1
        for ent in sample.get("comparison", {}).get("only_in_langextract", []):
            lbl = ent.get("label", "")
            label_discrepancies[lbl] = label_discrepancies.get(lbl, 0) + 1

    with (reports_dir / "state_matrix.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=["status", "count"])
        writer.writeheader()
        for status, count in sorted(status_counts.items()):
            writer.writerow({"status": status, "count": count})

    with (reports_dir / "top_discrepancies.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=["label", "count"])
        writer.writeheader()
        for label, count in sorted(
            label_discrepancies.items(), key=lambda kv: kv[1], reverse=True
        ):
            writer.writerow({"label": label, "count": count})

    representatives: dict[str, list[dict[str, Any]]] = {
        "exact_match": [],
        "partial_match": [],
        "ner_only": [],
        "langextract_only": [],
        "mixed": [],
    }
    for sample in samples:
        status = sample.get("comparison", {}).get("status")
        if status not in representatives:
            continue
        if len(representatives[status]) >= 10:
            continue
        representatives[status].append(
            {
                "sample_id": sample.get("sample_id"),
                "document_id": sample.get("document_id"),
                "paragraph_id": sample.get("paragraph_id"),
                "text": sample.get("text", "")[:500],
                "status": status,
                "ner_count": len(sample.get("ner_predictions", [])),
                "langextract_count": len(sample.get("langextract_predictions", [])),
            }
        )

    (reports_dir / "representative_samples.json").write_text(
        json.dumps(representatives, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_experiment(config_path: str) -> None:
    config = load_experiment_config(config_path)
    run_name = render_run_name(config.experiment.run_name, config.langextract.model_id)
    paths = _ensure_dirs(config, run_name)

    mapping = _load_mapping(config.mapping.labels_yaml_path)
    mapping_hash = sha256_file(Path(config.mapping.labels_yaml_path))

    examples = load_examples_from_yaml(config.langextract.examples_yaml_path)
    if not examples:
        raise ValueError("LangExtract examples_yaml_path contains no examples.")

    mlflow_setup = configure_mlflow(config)
    if isinstance(mlflow_setup, tuple):
        mlflow_enabled, mlflow_experiment_id = mlflow_setup
    else:
        # Backward compatibility for tests/mocks returning bool only.
        mlflow_enabled = bool(mlflow_setup)
        mlflow_experiment_id = None
    run_context = (
        mlflow.start_run(run_name=run_name, experiment_id=mlflow_experiment_id)
        if mlflow_enabled
        else nullcontext()
    )
    if not mlflow_enabled:
        logger.warning("Running without MLflow tracking for this execution.")

    with run_context:
        if mlflow_enabled:
            mlflow.set_tags(
                {
                    "experiment_name": config.experiment.name,
                    "pipeline": "ner_langextract_alignment",
                }
            )
            mlflow.log_param("mlflow_experiment_id", mlflow_experiment_id or "")
            mlflow.log_param("config_path", config_path)

        samples_input: list[dict[str, Any]] = []
        input_manifest: dict[str, Any]

        session = requests.Session()
        if config.data.input_paragraphs_jsonl:
            samples_input = _load_input_paragraphs(config)
            input_manifest = build_paragraph_manifest(samples_input)
        elif config.data.input_hf_dataset:
            samples_input = _load_input_hf_dataset(config)
            input_manifest = build_paragraph_manifest(samples_input)
        elif config.data.input_bio_txt:
            samples_input = _load_input_bio_txt(config)
            input_manifest = build_paragraph_manifest(samples_input)
        else:
            samples_input, input_manifest = _extract_paragraphs_from_docs(
                config=config,
                session=session,
            )

        if config.data.deduplicate_by_text:
            samples_input = _deduplicate_samples_by_text(samples_input)

        model = build_tracing_model(config.langextract)
        samples_output: list[dict[str, Any]] = []
        traces = []

        for sample in tqdm(samples_input, desc="align-paragraphs"):
            text = sample["text"]
            if not text.strip():
                continue
            logger.info(
                "align sample: sample_id=%s document_id=%s paragraph_id=%s chars=%s",
                sample.get("sample_id"),
                sample.get("document_id"),
                sample.get("paragraph_id"),
                len(text),
            )

            ner_payload, ner_ms = call_anonymizer_predict(
                session,
                base_url=config.api.base_url,
                path=config.api.anonymizer_predict_path,
                text=text,
                use_cache=config.api.use_cache,
                timeout_s=config.api.timeout_s,
                retries=config.api.retries,
                retry_backoff_s=config.api.retry_backoff_s,
            )

            try:
                lx_payload, lx_traces, lx_ms = run_langextract(
                    sample_id=sample["sample_id"],
                    text=text,
                    config=config.langextract,
                    examples=examples,
                    model=model,
                )
            except Exception as exc:
                logger.warning(
                    "langextract failed for sample_id=%s after retries: %s",
                    sample["sample_id"],
                    exc,
                )
                lx_payload = {
                    "document_id": sample["sample_id"],
                    "text": text,
                    "extractions": [],
                    "error": str(exc),
                }
                lx_ms = 0.0
                lx_traces = [
                    LLMTrace(
                        trace_id=f"fallback-{sample['sample_id']}",
                        sample_id=sample["sample_id"],
                        provider=config.langextract.provider,
                        model=config.langextract.model_id,
                        prompt="",
                        input_text=text,
                        raw_output=None,
                        parsed_output=lx_payload,
                        duration_ms=0.0,
                        error=str(exc),
                        metadata={"fallback_empty_extractions": True},
                    )
                ]
            traces.extend(lx_traces)

            record = _record_from_paragraph(
                sample_id=sample["sample_id"],
                document_id=sample["document_id"],
                paragraph_id=sample["paragraph_id"],
                source_path=sample.get("source_path"),
                text=text,
                ner_payload=ner_payload,
                langextract_payload=lx_payload,
                ner_latency_ms=ner_ms,
                lx_latency_ms=lx_ms,
                mapping=mapping,
                config=config,
            )
            samples_output.append(record)

        serialized_traces = serialize_traces_for_logging(traces, config)
        write_jsonl(paths["samples"], samples_output)
        write_jsonl(paths["traces_jsonl"], serialized_traces)
        write_traces_summary_csv(paths["traces_csv"], traces)

        _write_reports(samples_output, paths["reports"])

        ls_paths: dict[str, Path] = {}
        decisions: dict[str, dict[str, Any]] = {}
        if config.labelstudio.enabled:
            ls_export_dir = paths.get("labelstudio")
            if ls_export_dir is None:
                raise ValueError(
                    "Label Studio is enabled but export directory is not configured."
                )
            ls_paths = export_labelstudio_tasks(
                samples=samples_output,
                export_dir=ls_export_dir,
                qa_sample_rate=config.labelstudio.qa_sample_rate,
                qa_seed=config.labelstudio.qa_seed,
            )

            if config.labelstudio.import_annotations_path:
                tasks = load_labelstudio_tasks(
                    Path(config.labelstudio.import_annotations_path)
                )
                decisions = parse_labelstudio_decisions(tasks)

        (
            train_candidates,
            review_required,
        ) = consolidate_datasets(samples_output, decisions)
        write_jsonl(paths["train_candidates"], train_candidates)
        write_jsonl(paths["review_required"], review_required)

        metrics = summarize_metrics(samples_output, traces)

        if mlflow_enabled:
            log_run_metadata(
                config,
                run_name=run_name,
                mapping_hash=mapping_hash,
                dataset_hash=input_manifest.get("dataset_hash", ""),
                metrics=metrics,
            )

        _save_json(paths["base"] / "manifest.json", input_manifest)

        if mlflow_enabled:
            safe_log_artifact(str(paths["samples"]), artifact_path="comparisons")
            safe_log_artifact(str(paths["traces_jsonl"]), artifact_path="llm_traces")
            safe_log_artifact(str(paths["traces_csv"]), artifact_path="llm_traces")
            safe_log_artifact(
                str(paths["base"] / "manifest.json"), artifact_path="data"
            )
            if config.labelstudio.enabled:
                for p in ls_paths.values():
                    safe_log_artifact(str(p), artifact_path="labelstudio_export")
            safe_log_artifacts(str(paths["reports"]), artifact_path="reports")

        if config.logging.privacy.log_raw_predictions:
            raw_path = paths["raw"] / "samples_raw.json"
            _save_json(raw_path, samples_output)
            if mlflow_enabled:
                safe_log_artifact(str(raw_path), artifact_path="predictions_raw")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run NER + LangExtract alignment experiment from YAML config."
    )
    parser.add_argument(
        "--config", required=True, help="Path to experiment YAML config"
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    started = time.perf_counter()
    run_experiment(args.config)
    elapsed = time.perf_counter() - started
    logger.info(f"run completed in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
