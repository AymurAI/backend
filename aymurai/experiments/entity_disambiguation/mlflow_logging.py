from __future__ import annotations

import json
import tempfile
from pathlib import Path

import mlflow

from aymurai.experiments.entity_disambiguation.config import ExperimentRunConfig
from aymurai.experiments.entity_disambiguation.manifest import DatasetInfo
from aymurai.utils.yaml_data import save_yaml


def configure_mlflow(config: ExperimentRunConfig) -> None:
    mlflow.set_tracking_uri(config.logging.mlflow.tracking_uri)
    mlflow.set_experiment(config.logging.mlflow.experiment_name)


def log_run_metadata(
    config: ExperimentRunConfig,
    *,
    run_name: str | None = None,
    preds_dir_name: str | None = None,
    dataset_info: DatasetInfo | None = None,
    metrics: dict[str, float] | None = None,
    per_doc_scores: dict[str, object] | None = None,
) -> None:
    params = {
        "model_provider": config.model.provider,
        "model_name": config.model.name,
        "system_prompt_id": config.prompts.system.id,
        "user_prompt_id": config.prompts.user.id,
        "preds_dir_template": config.predictions.dir_name_template,
    }
    if run_name:
        params["run_name"] = run_name
    if preds_dir_name:
        params["preds_dir_name"] = preds_dir_name
    if config.model.temperature is not None:
        params["temperature"] = config.model.temperature
    if config.model.max_tokens is not None:
        params["max_tokens"] = config.model.max_tokens
    if config.data.dataset_id:
        params["dataset_id"] = config.data.dataset_id

    if dataset_info:
        params.update(
            {
                "dataset_hash": dataset_info.dataset_hash,
                "dataset_count": dataset_info.dataset_count,
                "dataset_bytes_total": dataset_info.dataset_bytes_total,
            }
        )

    mlflow.log_params(params)

    if metrics:
        mlflow.log_metrics(metrics)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config_payload = config.model_dump(mode="json")
        if not config.logging.privacy.log_prompt_text:
            config_payload["prompts"]["system"]["text"] = ""
            config_payload["prompts"]["user"]["text"] = ""
        config_path = tmp_path / "config.yaml"
        save_yaml(config_payload, str(config_path))
        mlflow.log_artifact(str(config_path), artifact_path="config")

        if config.logging.privacy.log_prompt_text:
            system_path = tmp_path / "system_prompt.txt"
            user_path = tmp_path / "user_prompt.txt"
            system_path.write_text(config.prompts.system.text or "", encoding="utf-8")
            user_path.write_text(config.prompts.user.text or "", encoding="utf-8")
            mlflow.log_artifact(str(system_path), artifact_path="prompts")
            mlflow.log_artifact(str(user_path), artifact_path="prompts")

        if (
            config.logging.privacy.log_data_manifest
            and dataset_info
            and dataset_info.manifest
        ):
            manifest_path = tmp_path / "manifest.json"
            manifest_path.write_text(
                json.dumps(dataset_info.manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            mlflow.log_artifact(str(manifest_path), artifact_path="data")

        if config.logging.privacy.log_per_doc_scores and per_doc_scores:
            scores_path = tmp_path / "per_doc_scores.json"
            scores_path.write_text(
                json.dumps(per_doc_scores, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            mlflow.log_artifact(str(scores_path), artifact_path="metrics")
