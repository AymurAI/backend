import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import ConfigDict, FilePath, field_validator
from pydantic_settings import BaseSettings

import aymurai

PARENT = Path(aymurai.__file__).parent


def load_env():
    load_dotenv(".env")

    # Load the stage-specific .env file (if it exists)
    stage = os.getenv("STAGE")
    if stage:
        env_file = f".env.{stage}"
        if os.path.exists(env_file):
            load_dotenv(env_file)


class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True)

    CORS_ORIGINS: list[str] | str = ",".join(
        [
            "http://localhost",
            "https://localhost",
            "http://localhost:8080",
            "http://localhost:3000",
            "0.0.0.0:8899",
            "0.0.0.0:3000",
        ]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v) -> list[str]:
        if v is None:
            return []

        if not isinstance(v, str):
            raise ValueError(v)

        return [i.strip() for i in v.split(",")]

    SQLALCHEMY_DATABASE_URI: str = "sqlite:////resources/cache/sqlite/database.db"

    RESOURCES_BASEPATH: str = "/resources"

    # Alembic Config for running migrations
    ALEMBIC_INI_PATH: FilePath = PARENT / "alembic.ini"

    ENV: str | None = None

    # Cachetools settings
    MEMORY_CACHE_MAXSIZE: int = 1
    MEMORY_CACHE_TTL: int = 60

    LIBREOFFICE_BIN: str = "libreoffice"

    # Disambiguation Config

    # Fuzzy Matching
    THRESHOLD: int = 70
    ANONYMIZER_PREDICT_BATCH_SIZE: int = 1

    # Data extraction (defensoria) — organigram cross-reference search backend.
    # "fuzzy" (rapidfuzz), "embeddings" (sentence-transformers + BM25), and
    # "hybrid" (weighted combination of both) are being A/B tested; keep this
    # switchable without a redeploy.
    DATA_EXTRACTION_SEARCH_BACKEND: Literal["fuzzy", "embeddings", "hybrid"] = "hybrid"
    DATA_EXTRACTION_TOP_K: int = 5
    # Weight given to the embeddings score in "hybrid" mode (fuzzy gets 1 - this).
    # 0.25 (favoring fuzzy) is the default sector_mode="hierarchy" was tuned
    # against -- see notebooks/experiments/defensoria/README.md.
    DATA_EXTRACTION_HYBRID_WEIGHT: float = 0.25
    # How many sector-corpus matches to consider per organigram candidate
    # when inferring `sector` (not just the single best one per candidate).
    # Only used when DATA_EXTRACTION_SECTOR_MODE="csv".
    DATA_EXTRACTION_SECTOR_TOP_K: int = 3
    # Discount applied to nombre-origin candidates (vs. cargo-origin, always
    # 1.0) when inferring `sector` -- nombre-search scores tend to run higher
    # than cargo-search scores on pure text similarity (full names either
    # match almost exactly or not at all), even though cargo is the more
    # durable signal across a change of government. 0.0 discards nombre-origin
    # evidence for `sector` entirely -- see notebooks/experiments/defensoria/README.md.
    DATA_EXTRACTION_NOMBRE_ORIGEN_WEIGHT: float = 0.0
    # How to resolve `sector` from the organigram candidates: "csv" matches
    # against destinatario_por_sector.csv, "hierarchy" reads it directly off
    # the organigram's own hierarchy, ignoring the CSV entirely. Default is
    # "hierarchy": destinatario_por_sector.csv only covers 16 sectors (the
    # organigram has ~30) and isn't kept in sync with it -- see
    # notebooks/experiments/defensoria/README.md.
    DATA_EXTRACTION_SECTOR_MODE: Literal["csv", "hierarchy"] = "hierarchy"

    @field_validator("ANONYMIZER_PREDICT_BATCH_SIZE")
    @classmethod
    def validate_anonymizer_predict_batch_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("ANONYMIZER_PREDICT_BATCH_SIZE must be >= 1")
        return v

    # LLM
    MODEL: str = "gemma4:latest"
    MODEL_CONTEXT: int = 9500
    TEMPERATURE: float = 0.0
    CONTEXT_WINDOW_LENGTH: int | None = 120
    TOKEN_LIMIT_FRAC: float = 2 / 3
    TOKENIZER_MODEL: str = "microsoft/phi-4"
    DECOMPOSE_BY: int | None = None

    # Label policies (JSON dict: label -> {disambiguation, anonymize})
    DISAMBIGUATION_LABEL_POLICIES: dict | None = None

    @field_validator("DISAMBIGUATION_LABEL_POLICIES", mode="before")
    @classmethod
    def parse_label_policies(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return json.loads(v)
        return v

    # Render policy (JSON dict)
    RENDER_POLICY: dict | None = None

    @field_validator("RENDER_POLICY", mode="before")
    @classmethod
    def parse_render_policy(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return json.loads(v)
        return v


load_env()
settings = Settings()
