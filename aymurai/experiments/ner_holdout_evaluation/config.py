from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aymurai.utils.yaml_data import load_yaml


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "ner-holdout-evaluation"
    run_name: str = "{backend}-{model}-{timestamp}"


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["conll_bio", "hf_token_classification", "span_jsonl"]
    input_path: str
    sample_id_field: str = "sample_id"
    text_field: str = "text"
    tokens_field: str = "tokens"
    tags_field: str = "tags"
    spans_field: str = "spans"
    label_field: str = "label"
    start_field: str = "start"
    end_field: str = "end"
    id2label: dict[str, str] | None = None
    max_samples: int | None = None
    deduplicate_by_text: bool = True


class BackendConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["ner_api", "langextract"] = "ner_api"


class APIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://localhost:8899"
    anonymizer_predict_path: str = "/anonymizer/predict"
    timeout_s: float = 60.0
    retries: int = 2
    retry_backoff_s: float = 1.0
    use_cache: bool = False


class LangExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["ollama", "openai"] = "ollama"
    model_id: str = "gpt-oss:20b"
    base_url: str = "http://localhost:11434/v1"
    api_key_env: str = "OLLAMA_API_KEY"
    api_key_fallback: str = "ollama"
    prompt_description: str
    examples_yaml_path: str
    temperature: float | None = 0.0
    max_tokens: int | None = 4096
    think: bool = False
    request_timeout_s: float = 120.0
    retries: int = 2
    retry_backoff_s: float = 1.0
    max_workers: int = 1
    extraction_passes: int = 1
    batch_length: int = 1


class MappingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels_yaml_path: str | None = None


class ComparisonConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalize_case: bool = True
    normalize_accents: bool = True
    normalize_punctuation: bool = True


class MetricsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_token_relaxed: bool = True
    perfect_definition: Literal["span_set_exact"] = "span_set_exact"


class MLflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    tracking_uri: str
    experiment_name: str = "ner-holdout-evaluation"
    enable_openai_autolog: bool = False
    request_timeout_s: float = 15
    request_max_retries: int = 2


class LoggingPrivacyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_prompt_text: bool = True
    log_llm_outputs: bool = True
    log_raw_predictions: bool = True
    redact_sensitive_fields: bool = False


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mlflow: MLflowConfig
    privacy: LoggingPrivacyConfig = LoggingPrivacyConfig()


class OutputsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_dir: str
    samples_gold_jsonl: str = "samples_gold.jsonl"
    predictions_jsonl: str = "predictions.jsonl"
    per_sample_scores_jsonl: str = "per_sample_scores.jsonl"
    metrics_summary_json: str = "metrics_summary.json"
    strict_label_metrics_csv: str = "reports/label_metrics.csv"
    token_relaxed_confusion_csv: str = "reports/token_relaxed_confusion.csv"
    feedback_jsonl: str = "feedback/perfect_prediction.jsonl"
    traces_jsonl: str = "llm_traces/traces.jsonl"
    traces_summary_csv: str = "llm_traces/traces_summary.csv"
    manifest_json: str = "manifest.json"


class NERHoldoutEvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment: ExperimentConfig = ExperimentConfig()
    data: DataConfig
    backend: BackendConfig = BackendConfig()
    api: APIConfig = APIConfig()
    langextract: LangExtractConfig | None = None
    mapping: MappingConfig = MappingConfig()
    comparison: ComparisonConfig = ComparisonConfig()
    metrics: MetricsConfig = MetricsConfig()
    logging: LoggingConfig
    outputs: OutputsConfig

    @model_validator(mode="after")
    def validate_backend_requirements(self) -> "NERHoldoutEvaluationConfig":
        if self.backend.mode == "langextract":
            if self.langextract is None:
                raise ValueError(
                    "langextract config is required when backend.mode=langextract"
                )
            if not self.mapping.labels_yaml_path:
                raise ValueError(
                    "mapping.labels_yaml_path is required when backend.mode=langextract"
                )
        return self


def load_experiment_config(path: str) -> NERHoldoutEvaluationConfig:
    data = load_yaml(path)
    env_tracking = os.getenv("MLFLOW_TRACKING_URI")
    if env_tracking:
        data.setdefault("logging", {}).setdefault("mlflow", {})[
            "tracking_uri"
        ] = env_tracking

    return NERHoldoutEvaluationConfig.model_validate(data)


def render_run_name(
    template: str,
    *,
    backend: str,
    model_name: str,
    timestamp: str | None = None,
) -> str:
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%y%m%d_%H%M")
    return template.format(backend=backend, model=model_name, timestamp=timestamp)
