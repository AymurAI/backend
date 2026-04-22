from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aymurai.utils.yaml_data import load_yaml


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    odt_paths: list[str]
    less_frequent_labels_path: str
    original_train_unique_labels_path: str
    output_dir: str
    run_dir_name_template: str = "{timestamp}"
    jsonl_filename: str = "augmented_paragraphs.jsonl"
    bio_filename: str = "augmented_train.txt"
    alignments_dirname: str = "alignments"


class APIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://localhost:8000"
    document_extract_path: str = "/misc/document-extract"
    timeout_s: float = 300.0


class OllamaConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["ollama", "openai"] = "ollama"
    model: str = "qwen3:8b"
    keep_alive: str = "5m"
    num_ctx: int = 8192
    temperature: float = 0.0
    allow_missing_labels: bool = True
    allow_non_faker_values: bool = True


class OpenAIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = "gpt-4.1-mini"
    api_key_env_var: str = "OPENAI_API_KEY"
    base_url: str | None = None
    temperature: float = 0.0


class GenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_label_count: int | None = None
    candidates_per_label: int = 5
    max_attempts_per_label: int = 50
    max_paragraphs: int | None = None
    run_with_ollama: bool = True


class NormalizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fuzzy_threshold: float = 0.75
    strict_require_all_raw_labels_mapped: bool = True
    exact_map: dict[str, str] = Field(default_factory=dict)


class DataAugmentationRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: PathsConfig
    api: APIConfig = APIConfig()
    ollama: OllamaConfig = OllamaConfig()
    openai: OpenAIConfig = OpenAIConfig()
    generation: GenerationConfig = GenerationConfig()
    normalization: NormalizationConfig = NormalizationConfig()


def find_project_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "aymurai").exists():
            return candidate
    raise RuntimeError(f"Could not locate the project root from {start}")


def resolve_config_path(value: str, *, project_root: Path) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((project_root / path).resolve())


def render_run_dir_name(template: str, *, timestamp: str | None = None) -> str:
    run_timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return template.format(timestamp=run_timestamp)


def load_data_augmentation_config(path: str | Path) -> DataAugmentationRunConfig:
    config_path = Path(path).resolve()
    payload = load_yaml(str(config_path))
    project_root = find_project_root(config_path.parent)

    paths_payload = payload.setdefault("paths", {})
    path_keys = (
        "less_frequent_labels_path",
        "original_train_unique_labels_path",
        "output_dir",
    )
    for key in path_keys:
        if key in paths_payload:
            paths_payload[key] = resolve_config_path(
                paths_payload[key], project_root=project_root
            )

    if "odt_paths" in paths_payload:
        paths_payload["odt_paths"] = [
            resolve_config_path(item, project_root=project_root)
            for item in paths_payload["odt_paths"]
        ]

    return DataAugmentationRunConfig.model_validate(payload)
