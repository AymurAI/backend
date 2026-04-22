from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from aymurai.utils.yaml_data import load_yaml


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "synthetic-paragraph-generation"
    run_name: str = "{model}_{timestamp}"


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_paths: list[str] = Field(
        validation_alias=AliasChoices(
            "source_paths", "source_path", "examples_jsonl_path"
        )
    )
    guidelines_path: str | None = None
    text_field: str = "resolved_text"
    labels_field: str = "labels"
    max_examples: int | None = None
    examples_per_label: int = Field(
        default=3,
        validation_alias=AliasChoices("examples_per_label", "examples_per_prompt"),
    )
    normalized_labels_path: str | None = None


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = "qwen3:8b"
    keep_alive: str = "5m"
    num_ctx: int = 8192
    max_context_tokens: int = 8192
    reserved_output_tokens: int = 1024
    token_encoding_name: str = "cl100k_base"
    temperature: float = 0.2
    max_retries_per_sample: int = 2
    paragraphs_per_call: int = 1


class FakerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates_per_label: int = 5
    max_attempts_per_label: int = 50
    llm_only_labels: list[str] = Field(default_factory=lambda: ["TEXTO_ANONIMIZAR"])


class SamplingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_total_synthetic: int = Field(
        default=50,
        validation_alias=AliasChoices("target_total_synthetic", "total_paragraphs"),
    )
    desired_target_labels: list[str] | None = None
    seed: int = 42


class SimilarityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    threshold: float = 95.0
    internal_enabled: bool = True
    internal_threshold: float = 95.0
    train_set_path: str | None = None
    dev_set_path: str | None = None
    test_set_path: str | None = None
    extra_bio_paths: list[str] = Field(default_factory=list)


class OutputsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_dir: str
    run_dir_name_template: str = "{timestamp}"
    samples_jsonl: str = "synthetic_samples.jsonl"
    bio_txt: str = "synthetic_samples.txt"
    report_json: str = "report.json"
    prompts_jsonl: str = "llm_prompts.jsonl"


class SyntheticParagraphGenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment: ExperimentConfig = ExperimentConfig()
    data: DataConfig
    llm: LLMConfig = LLMConfig()
    faker: FakerConfig = FakerConfig()
    sampling: SamplingConfig = SamplingConfig()
    similarity: SimilarityConfig = SimilarityConfig()
    outputs: OutputsConfig


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "aymurai").exists():
            return candidate
    raise RuntimeError(f"Could not locate the project root from {start}")


def resolve_config_path(value: str | None, *, project_root: Path) -> str | None:
    if value is None:
        return None
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((project_root / path).resolve())


def render_run_dir_name(template: str, *, timestamp: str | None = None) -> str:
    run_timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return template.format(timestamp=run_timestamp)


def load_synthetic_paragraph_generation_config(
    path: str | Path,
) -> SyntheticParagraphGenerationConfig:
    config_path = Path(path).resolve()
    payload = load_yaml(str(config_path))
    project_root = find_project_root(config_path.parent)

    data_payload = payload.setdefault("data", {})
    source_key = next(
        (
            k
            for k in ("source_paths", "source_path", "examples_jsonl_path")
            if k in data_payload
        ),
        "source_paths",
    )
    raw_paths = data_payload.get(source_key, [])

    if isinstance(raw_paths, str):
        raw_paths = [raw_paths]

    data_payload["source_paths"] = [
        resolve_config_path(p, project_root=project_root) for p in raw_paths
    ]
    data_payload.pop("source_path", None)
    data_payload.pop("examples_jsonl_path", None)

    if "guidelines_path" in data_payload:
        data_payload["guidelines_path"] = resolve_config_path(
            data_payload["guidelines_path"], project_root=project_root
        )
    if "normalized_labels_path" in data_payload:
        data_payload["normalized_labels_path"] = resolve_config_path(
            data_payload["normalized_labels_path"], project_root=project_root
        )

    outputs_payload = payload.setdefault("outputs", {})
    if "base_dir" in outputs_payload:
        outputs_payload["base_dir"] = resolve_config_path(
            outputs_payload["base_dir"], project_root=project_root
        )

    similarity_payload = payload.setdefault("similarity", {})
    for key in ("train_set_path", "dev_set_path", "test_set_path"):
        if key in similarity_payload:
            similarity_payload[key] = resolve_config_path(
                similarity_payload[key], project_root=project_root
            )
    if "extra_bio_paths" in similarity_payload:
        similarity_payload["extra_bio_paths"] = [
            resolve_config_path(path, project_root=project_root)
            for path in (similarity_payload.get("extra_bio_paths") or [])
        ]

    return SyntheticParagraphGenerationConfig.model_validate(payload)
