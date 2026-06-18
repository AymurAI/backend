from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from aymurai.experiments.mlflow_utils import (
    LoggingConfig,
    MLflowConfig,
    resolve_tracking_uri,
)
from aymurai.utils.yaml_data import load_yaml


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    train_set_path: str
    dev_set_path: str
    test_set_path: str
    candidate_input_paths: list[str]
    output_dir: str
    low_frequency_labels_path: str | None = None
    run_dir_name_template: str = "{strategy}_{timestamp}"
    clean_labeled_filename: str = "clean_labeled_candidates.jsonl"
    clean_unlabeled_filename: str = "clean_unlabeled_candidates.jsonl"
    selected_candidates_filename: str = "selected_candidates.jsonl"
    final_bio_filename: str = "train_generated.txt"
    report_filename: str = "report.json"
    low_frequency_labels_filename: str = "resolved_low_frequency_labels.txt"
    dataset_composition_report_filename: str = "dataset_composition_report.json"


class DeduplicationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    internal_threshold: float = 95.0
    corpus_threshold: float = 95.0


class LabelSelectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "all_clean_labeled"
    low_frequency_top_k: int = 15
    min_target_labels_per_candidate: int = 1

    @model_validator(mode="after")
    def validate_mode(self) -> "LabelSelectionConfig":
        allowed_modes = {"all_clean_labeled", "low_frequency_only"}
        if self.mode not in allowed_modes:
            raise ValueError(
                f"label_selection.mode must be one of {sorted(allowed_modes)}"
            )
        return self


class UnlabeledSamplingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "target_total_background_ratio"
    target_background_to_labeled_ratio: float = Field(
        default=1.0,
        validation_alias=AliasChoices("target_background_to_labeled_ratio", "ratio"),
    )
    fixed_count: int | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> "UnlabeledSamplingConfig":
        allowed_modes = {
            "none",
            "all",
            "ratio_to_selected_labeled",
            "target_total_background_ratio",
            "preserve_original_background_ratio",
            "fixed_count",
        }
        if self.mode not in allowed_modes:
            raise ValueError(
                f"unlabeled_sampling.mode must be one of {sorted(allowed_modes)}"
            )
        if self.mode == "fixed_count" and self.fixed_count is None:
            raise ValueError(
                "unlabeled_sampling.fixed_count is required when mode='fixed_count'"
            )
        if self.target_background_to_labeled_ratio < 0:
            raise ValueError(
                "unlabeled_sampling.target_background_to_labeled_ratio must be >= 0"
            )
        return self


class AssemblyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_original_train: bool = True
    shuffle_selected_candidates: bool = True
    seed: int = 42


class TrainingDatasetGenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: PathsConfig
    deduplication: DeduplicationConfig = DeduplicationConfig()
    label_selection: LabelSelectionConfig = LabelSelectionConfig()
    unlabeled_sampling: UnlabeledSamplingConfig = UnlabeledSamplingConfig()
    assembly: AssemblyConfig = AssemblyConfig()
    logging: LoggingConfig = LoggingConfig(
        mlflow=MLflowConfig(experiment_name="training-dataset-generation")
    )


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


def build_strategy_slug(config: TrainingDatasetGenerationConfig) -> str:
    train_mode = "merge_old" if config.assembly.include_original_train else "new_only"
    return "__".join(
        [
            train_mode,
            config.label_selection.mode,
            config.unlabeled_sampling.mode,
        ]
    )


def render_run_dir_name(
    template: str,
    *,
    timestamp: str | None = None,
    strategy: str,
) -> str:
    run_timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return template.format(timestamp=run_timestamp, strategy=strategy)


def load_training_dataset_generation_config(
    path: str | Path,
) -> TrainingDatasetGenerationConfig:
    config_path = Path(path).resolve()
    payload = load_yaml(str(config_path))
    project_root = find_project_root(config_path.parent)

    paths_payload = payload.setdefault("paths", {})
    for key in (
        "train_set_path",
        "dev_set_path",
        "test_set_path",
        "output_dir",
        "low_frequency_labels_path",
    ):
        if key in paths_payload:
            paths_payload[key] = resolve_config_path(
                paths_payload[key], project_root=project_root
            )

    if "candidate_input_paths" in paths_payload:
        paths_payload["candidate_input_paths"] = [
            resolve_config_path(item, project_root=project_root)
            for item in paths_payload["candidate_input_paths"]
        ]

    mlflow_payload = payload.setdefault("logging", {}).setdefault("mlflow", {})
    if "tracking_uri" in mlflow_payload:
        mlflow_payload["tracking_uri"] = resolve_tracking_uri(
            mlflow_payload["tracking_uri"], project_root=project_root
        )

    return TrainingDatasetGenerationConfig.model_validate(payload)
