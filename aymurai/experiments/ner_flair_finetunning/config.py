from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from aymurai.utils.yaml_data import load_yaml


class ExperimentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "ner-flair-finetuning"
    run_name: str = "{backend}-{model}-{timestamp}"


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_path: str
    train_file: str = "train.txt"
    dev_file: str = "dev.txt"
    test_file: str = "test.txt"


class BackendConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["pretrained_flair", "base_flair"] = "pretrained_flair"


class FlairModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finetune_from: str | None = None
    model_id: str = "dccuchile/bert-base-spanish-wwm-cased"
    fine_tune: bool = True
    use_context: bool = True
    hidden_size: int = 256
    use_crf: bool = True
    use_rnn: bool = True
    reproject_embeddings: bool = True
    flair_forward: str = "es-forward"
    flair_backward: str = "es-backward"


class TrainingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: str = "auto"
    learning_rate: float = 5.0e-5
    mini_batch_size: int = 4
    mini_batch_chunk_size: int = 1
    max_epochs: int = 10
    weight_decay: float = 0.0
    anneal_factor: float = 0.5
    patience: int = 3
    min_learning_rate: float = 1.0e-7
    embeddings_storage_mode: str = "none"
    save_model_each_k_epochs: int = 1
    dev_eval_start_epoch: int = 1
    dev_eval_every_k_epochs: int = 1
    test_eval_epoch: int | None = None


class ComparisonConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalize_case: bool = True
    normalize_accents: bool = True
    normalize_punctuation: bool = True


class MetricsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_token_relaxed: bool = True


class MLflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    tracking_uri: str = "http://localhost:5005"
    experiment_name: str = "aymurai-ner-flair-finetuning"
    request_timeout_s: float = 15.0
    request_max_retries: int = 2
    enable_span_comparison_traces: bool = True
    max_traces_per_split: int | None = 300


class LoggingPrivacyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_predictions: bool = True
    log_metrics: bool = True
    redact_sensitive_fields: bool = False


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mlflow: MLflowConfig
    privacy: LoggingPrivacyConfig = LoggingPrivacyConfig()


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_dir: str
    create_run_subdir: bool = True
    run_subdir_template: str = "{run_name}"
    samples_gold_jsonl: str = "samples_gold.jsonl"
    predictions_jsonl: str = "predictions.jsonl"
    per_sample_scores_jsonl: str = "per_sample_scores.jsonl"
    comparisons_jsonl: str = "comparisons.jsonl"
    comparisons_csv: str = "comparisons.csv"
    comparisons_html: str = "comparisons.html"
    metrics_summary_json: str = "metrics_summary.json"
    strict_label_metrics_csv: str = "reports/strict_label_metrics.csv"
    token_relaxed_confusion_csv: str = "reports/token_relaxed_confusion.csv"
    manifest_json: str = "manifest.json"


class NERFinetuningConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    experiment: ExperimentMetadata = ExperimentMetadata()
    data: DataConfig
    backend: BackendConfig = BackendConfig()
    flair_model: FlairModelConfig = FlairModelConfig()
    training: TrainingConfig = TrainingConfig()
    comparison: ComparisonConfig = ComparisonConfig()
    metrics: MetricsConfig = MetricsConfig()
    logging: LoggingConfig
    outputs: OutputConfig

    @model_validator(mode="before")
    @classmethod
    def _compat_backend_mode(cls, data: Any) -> Any:
        if isinstance(data, dict) and "backend" not in data and "backend_mode" in data:
            data["backend"] = data["backend_mode"]
        return data

    @model_validator(mode="after")
    def validate_backend_requirements(self) -> "NERFinetuningConfig":
        if (
            self.backend.mode == "pretrained_flair"
            and not self.flair_model.finetune_from
        ):
            raise ValueError(
                "flair_model.finetune_from is required when backend.mode=pretrained_flair"
            )
        return self


def load_experiment_config(path: str) -> NERFinetuningConfig:
    data = load_yaml(path)
    env_tracking = os.getenv("MLFLOW_TRACKING_URI")
    if env_tracking:
        data.setdefault("logging", {}).setdefault("mlflow", {})[
            "tracking_uri"
        ] = env_tracking

    return NERFinetuningConfig.model_validate(data)


def render_run_name(
    template: str,
    *,
    backend: str,
    model_name: str,
    timestamp: str | None = None,
) -> str:
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%y%m%d_%H%M")
    return template.format(backend=backend, model=model_name, timestamp=timestamp)
