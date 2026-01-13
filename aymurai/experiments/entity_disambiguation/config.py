import os
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aymurai.utils.yaml_data import load_yaml


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    run_name: str


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    name: str
    temperature: float | None = None
    max_tokens: int | None = None


class PromptSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str | None = None


class PromptsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: PromptSpec
    user: PromptSpec


class DataManifestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    mode: Literal["metadata_only"] = "metadata_only"


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ground_truth_dir: str
    input_dir: str
    dataset_id: str | None = None
    manifest: DataManifestConfig = DataManifestConfig()


class PredictionsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_base_dir: str
    dir_name_template: str


class MLflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tracking_uri: str
    experiment_name: str


class LoggingPrivacyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_prompt_text: bool = True
    log_data_manifest: bool = False
    log_per_doc_scores: bool = True


class PerDocScoresConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_strategy: str = "anon_filename"


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mlflow: MLflowConfig
    privacy: LoggingPrivacyConfig = LoggingPrivacyConfig()
    per_doc_scores: PerDocScoresConfig = PerDocScoresConfig()


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    function: str = "evaluate_disambiguation"
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "w_ent": 0.4,
            "w_alias": 0.35,
            "w_label": 0.2,
            "w_role": 0.05,
        }
    )
    per_doc_scores: bool = True
    sim_threshold: float | None = None
    normalize: bool = True


class ExperimentRunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment: ExperimentConfig
    model: ModelConfig
    prompts: PromptsConfig
    data: DataConfig
    predictions: PredictionsConfig
    logging: LoggingConfig
    evaluation: EvaluationConfig


def load_experiment_config(path: str) -> ExperimentRunConfig:
    """
    Load an experiment configuration from a YAML file.

    Args:
        path (str): Path to the YAML configuration file.

    Raises:
        ValueError: If the MLflow tracking URI is not set in the environment or configuration.

    Returns:
        ExperimentRunConfig: The loaded experiment configuration.
    """
    data = load_yaml(path)
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
    if tracking_uri:
        logging_cfg = data.setdefault("logging", {})
        mlflow_cfg = logging_cfg.setdefault("mlflow", {})
        mlflow_cfg["tracking_uri"] = tracking_uri
    else:
        mlflow_cfg = data.get("logging", {}).get("mlflow", {})
        if "tracking_uri" not in mlflow_cfg:
            raise ValueError(
                "MLFLOW_TRACKING_URI is required but was not set in the environment."
            )
    return ExperimentRunConfig.model_validate(data)


def render_run_name(
    template: str,
    model_name: str,
    system_id: str,
    user_id: str,
    *,
    timestamp: str | None = None,
) -> str:
    """
    Render a run name based on a template and provided identifiers.

    Args:
        template (str): The template string for the run name.
        model_name (str): The name of the model.
        system_id (str): The system identifier.
        user_id (str): The user identifier.
        timestamp (str | None, optional): The timestamp string. Defaults to None.

    Returns:
        str: The rendered run name.
    """
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%y%m%d_%H%M")
    return template.format(
        model=model_name,
        system_id=system_id,
        user_id=user_id,
        timestamp=timestamp,
    )
