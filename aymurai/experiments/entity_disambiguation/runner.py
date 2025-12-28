from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable

import mlflow
import requests
from more_itertools import unique_everseen
from tqdm import tqdm

from aymurai.evaluation.metrics import evaluate_disambiguation
from aymurai.experiments.entity_disambiguation.config import (
    load_experiment_config,
    render_run_name,
)
from aymurai.experiments.entity_disambiguation.manifest import build_metadata_manifest
from aymurai.experiments.entity_disambiguation.mlflow_logging import (
    configure_mlflow,
    log_run_metadata,
)
from aymurai.llm_providers import OllamaLLMProvider
from aymurai.logger import get_logger
from aymurai.meta.entities import CanonicalEntities, CanonicalEntity
from aymurai.utils.json_data import get_pretty, load_json, save_json
from aymurai.utils.paths import prediction_filename_for_test, test_id_from_filename

logger = get_logger(__name__)

DOC_EXTENSIONS = {".pdf", ".docx"}


def discover_documents(root: Path, extensions: Iterable[str]) -> list[Path]:
    extensions = {ext.lower() for ext in extensions}
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in extensions
    )


def call_extraction_api(
    session: requests.Session,
    endpoint: str,
    file_path: Path,
    timeout_s: float,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "path": str(file_path),
        "status": "failure",
        "status_code": None,
        "elapsed_s": None,
        "detail": None,
    }

    if not file_path.exists():
        payload["detail"] = "File does not exist"
        return payload

    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    files = {
        "file": (file_path.name, file_path.open("rb"), mime_type),
    }

    try:
        start = time.perf_counter()
        response = session.post(
            endpoint,
            files=files,
            timeout=timeout_s,
        )
        elapsed = time.perf_counter() - start
    except requests.RequestException as exc:
        payload["detail"] = f"Request failed: {exc}"
        return payload
    finally:
        files["file"][1].close()

    payload["status_code"] = response.status_code
    payload["elapsed_s"] = elapsed

    try:
        response_body = response.json()
    except ValueError:
        response_body = {"raw": response.text[:500]}

    if response.ok:
        payload["status"] = "success"
        payload["detail"] = {
            "document_id": response_body.get("document_id"),
            "document": response_body.get("document", []),
        }
    else:
        payload["detail"] = response_body

    return payload


def get_predictions(
    session: requests.Session,
    endpoint: str,
    sample: str,
    timeout_s: float,
) -> dict:
    response = session.post(url=endpoint, json={"text": sample}, timeout=timeout_s)
    response.raise_for_status()
    return response.json()


def parse_prediction_labels(predictions: list[dict[str, Any]]) -> list[dict[str, str]]:
    attrs_stream = (
        label.get("attrs") or {}
        for label in (label for pred in predictions for label in pred.get("labels", ()))
    )

    unique_pairs = unique_everseen(
        (
            attrs.get("aymurai_label"),
            attrs.get("aymurai_alt_text"),
        )
        for attrs in attrs_stream
        if attrs.get("aymurai_label") and attrs.get("aymurai_alt_text")
    )

    return sorted(
        ({"aymurai_label": label, "text": text} for label, text in unique_pairs),
        key=lambda item: (item["aymurai_label"], item["text"]),
    )


def sanitize_filename(path: Path) -> str:
    base = os.path.splitext(path.name)[0]
    target = re.sub(r"\s+|_", "-", base)
    target = re.sub(r"-{2,}", "-", target)
    return target


def extract_canonical_entities(
    *,
    session: requests.Session,
    doc_path: Path,
    extract_endpoint: str,
    predict_endpoint: str,
    timeout_s: float,
    model_name: str,
    system_prompt: str,
    user_prompt_template: str,
    temperature: float | None,
    max_tokens: int | None,
) -> list[CanonicalEntity]:
    document_payload = call_extraction_api(
        session,
        extract_endpoint,
        doc_path,
        timeout_s,
    )
    document = document_payload.get("detail", {}).get("document")

    if not document:
        raise ValueError("Document text is empty or not found.")

    ner_predictions = [
        get_predictions(session, predict_endpoint, paragraph, timeout_s)
        for paragraph in tqdm(document, desc=f"NER {doc_path.name}")
    ]
    parsed_ner_labels = parse_prediction_labels(ner_predictions)
    ner_output_json = get_pretty(parsed_ner_labels)

    user_prompt = user_prompt_template.format(
        document_text="\n".join(document).strip(),
        ner_output_json=ner_output_json,
    )

    provider = OllamaLLMProvider(model=model_name)
    options: dict[str, object] = {}
    if temperature is not None:
        options["temperature"] = temperature
    if max_tokens is not None:
        options["num_predict"] = max_tokens

    generate_kwargs: dict[str, object] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "format": CanonicalEntities.model_json_schema(),
    }
    if options:
        generate_kwargs["options"] = options

    response = provider.generate(**generate_kwargs)

    payload = json.loads(response.text)
    canonical_entities = [
        CanonicalEntity.model_validate(output)
        for output in payload.get("canonical_entities", [])
    ]

    return canonical_entities


def run_experiment(config_path: str) -> None:
    config = load_experiment_config(config_path)

    input_dir = Path(config.data.input_dir)
    ground_truth_dir = Path(config.data.ground_truth_dir)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    if not ground_truth_dir.exists():
        raise FileNotFoundError(f"Ground truth directory not found: {ground_truth_dir}")

    documents = discover_documents(input_dir, DOC_EXTENSIONS)
    if not documents:
        raise RuntimeError(f"No documents found under {input_dir}")

    timestamp = time.strftime("%y%m%d_%H%M")
    run_name = render_run_name(
        config.experiment.run_name,
        config.model.name,
        config.prompts.system.id,
        config.prompts.user.id,
        timestamp=timestamp,
    )
    preds_dir_name = render_run_name(
        config.predictions.dir_name_template,
        config.model.name,
        config.prompts.system.id,
        config.prompts.user.id,
        timestamp=timestamp,
    )
    output_dir = Path(config.predictions.output_base_dir) / preds_dir_name
    output_dir.mkdir(parents=True, exist_ok=False)

    dataset_info = (
        build_metadata_manifest(ground_truth_dir)
        if config.data.manifest.enabled
        else None
    )

    api_base_url = os.getenv("DOCUMENT_API_BASE_URL", "http://localhost:8899")
    extract_endpoint = f"{api_base_url}/misc/document-extract"
    predict_endpoint = f"{api_base_url}/anonymizer/predict"
    timeout_s = float(os.getenv("DOCUMENT_REQUEST_TIMEOUT", "30"))

    logger.info(f"Processing {len(documents)} documents from {input_dir}")
    logger.info(f"Predictions will be stored in {output_dir}")

    configure_mlflow(config)

    per_doc_scores: dict[str, object] = {}
    metrics_summary: dict[str, float] = {}

    with mlflow.start_run(run_name=run_name):
        session = requests.Session()

        processed = 0
        failed = 0

        for doc_path in documents:
            logger.info(f"Processing document: {doc_path.name}")
            try:
                canonical_entities = extract_canonical_entities(
                    session=session,
                    doc_path=doc_path,
                    extract_endpoint=extract_endpoint,
                    predict_endpoint=predict_endpoint,
                    timeout_s=timeout_s,
                    model_name=config.model.name,
                    system_prompt=config.prompts.system.text or "",
                    user_prompt_template=config.prompts.user.text or "",
                    temperature=config.model.temperature,
                    max_tokens=config.model.max_tokens,
                )
                target_filename = sanitize_filename(doc_path)
                target_path = output_dir / f"{target_filename}.json"
                save_json(
                    [
                        entity.model_dump()
                        | {
                            "entity_id": entity.entity_id.hex
                            if entity.entity_id
                            else None
                        }
                        for entity in canonical_entities
                    ],
                    str(target_path),
                )
                processed += 1
            except Exception as exc:
                failed += 1
                logger.warning(f"Error processing {doc_path.name}: {exc}")

        if config.evaluation.function != "evaluate_disambiguation":
            raise ValueError(
                f"Unsupported evaluation function: {config.evaluation.function}"
            )

        results = []
        if output_dir.exists():
            for test_path in sorted(ground_truth_dir.glob("*.json")):
                doc_id = test_id_from_filename(test_path)
                pred_path = output_dir / prediction_filename_for_test(test_path)

                if not pred_path.exists():
                    logger.warning(
                        f"Prediction for {test_path.name} was not found; skipping."
                    )
                    continue

                gold_data = load_json(str(test_path))
                pred_data = load_json(str(pred_path))

                score, metrics = evaluate_disambiguation(
                    gold_data,
                    pred_data,
                    w_ent=config.evaluation.weights.get("w_ent", 0.4),
                    w_alias=config.evaluation.weights.get("w_alias", 0.35),
                    w_label=config.evaluation.weights.get("w_label", 0.2),
                    w_role=config.evaluation.weights.get("w_role", 0.05),
                    sim_threshold=config.evaluation.sim_threshold or 0.3,
                    normalize=config.evaluation.normalize,
                )
                results.append((doc_id, score, metrics))

        average = (
            sum(score for _, score, _ in results) / len(results)
            if results
            else float("nan")
        )

        if results:
            metrics_summary["score_avg"] = average
            metrics_summary["doc_count"] = float(len(results))

            metric_names = set(results[0][2].keys())
            for metric_name in metric_names:
                metrics_summary[f"{metric_name}_avg"] = sum(
                    metrics.get(metric_name, 0.0) for _, _, metrics in results
                ) / len(results)

            for doc_id, score, metrics in results:
                per_doc_scores[doc_id] = {"score": score, **metrics}

        metrics_summary["docs_processed"] = float(processed)
        metrics_summary["docs_failed"] = float(failed)

        log_run_metadata(
            config,
            run_name=run_name,
            preds_dir_name=preds_dir_name,
            dataset_info=dataset_info,
            metrics=metrics_summary if metrics_summary else None,
            per_doc_scores=per_doc_scores if per_doc_scores else None,
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run entity disambiguation experiment from a YAML config.",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the experiment YAML config.",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    run_experiment(args.config)


if __name__ == "__main__":
    main()
