from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aymurai.utils.yaml_data import load_yaml


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "ner-langextract-alignment"
    run_name: str = "{model}-{timestamp}"


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_documents_dir: str | None = None
    input_paragraphs_jsonl: str | None = None
    input_bio_txt: str | None = None
    input_hf_dataset: str | None = None
    input_hf_config_name: str | None = None
    input_hf_split: str = "train"
    input_hf_text_column: str = "text"
    input_hf_sample_id_column: str | None = None
    input_hf_document_id_column: str | None = None
    input_hf_language_column: str | None = None
    input_hf_language_value: str | None = None
    input_hf_cache_dir: str | None = None
    include_extensions: list[str] = Field(default_factory=lambda: [".pdf", ".docx"])
    max_documents: int | None = None
    max_paragraphs: int | None = None
    deduplicate_by_text: bool = True

    @model_validator(mode="after")
    def validate_source(self) -> "DataConfig":
        if (
            not self.input_documents_dir
            and not self.input_paragraphs_jsonl
            and not self.input_bio_txt
            and not self.input_hf_dataset
        ):
            raise ValueError(
                "Set one input source: data.input_documents_dir, data.input_paragraphs_jsonl, data.input_bio_txt, or data.input_hf_dataset."
            )
        if self.input_hf_language_value and not self.input_hf_language_column:
            raise ValueError(
                "data.input_hf_language_column must be set when data.input_hf_language_value is provided."
            )
        return self


class APIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://localhost:8899"
    document_extract_path: str = "/misc/document-extract"
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

    labels_yaml_path: str


class ComparisonConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["exact_span_label"] = "exact_span_label"
    normalize_case: bool = True
    normalize_accents: bool = True
    normalize_punctuation: bool = True


class LabelStudioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    export_dir: str | None = None
    qa_sample_rate: float = 0.10
    qa_seed: int = 42
    import_annotations_path: str | None = None

    @model_validator(mode="after")
    def validate_export_dir(self) -> "LabelStudioConfig":
        if self.enabled and not self.export_dir:
            raise ValueError(
                "labelstudio.export_dir must be set when labelstudio.enabled=true."
            )
        return self


class MLflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    tracking_uri: str
    experiment_name: str = "ner-langextract-alignment"
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
    samples_jsonl: str = "samples.jsonl"
    traces_jsonl: str = "llm_traces/traces.jsonl"
    traces_summary_csv: str = "llm_traces/traces_summary.csv"
    train_candidates_jsonl: str = "train_candidates.jsonl"
    review_required_jsonl: str = "review_required.jsonl"


class NERLangExtractRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment: ExperimentConfig = ExperimentConfig()
    data: DataConfig
    api: APIConfig = APIConfig()
    langextract: LangExtractConfig
    mapping: MappingConfig
    comparison: ComparisonConfig = ComparisonConfig()
    labelstudio: LabelStudioConfig
    logging: LoggingConfig
    outputs: OutputsConfig


def load_experiment_config(path: str) -> NERLangExtractRunConfig:
    data = load_yaml(path)
    env_tracking = os.getenv("MLFLOW_TRACKING_URI")
    if env_tracking:
        data.setdefault("logging", {}).setdefault("mlflow", {})[
            "tracking_uri"
        ] = env_tracking

    return NERLangExtractRunConfig.model_validate(data)


def render_run_name(
    template: str, model_name: str, *, timestamp: str | None = None
) -> str:
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%y%m%d_%H%M")
    return template.format(model=model_name, timestamp=timestamp)
