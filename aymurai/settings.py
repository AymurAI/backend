import json
import os
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv
from pydantic import FilePath, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(case_sensitive=True)

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

    ENV: str | None = None
    RESOURCES_BASEPATH: str = "/resources"

    # --- Memory cache settings ----------------------------------------------
    MEMORY_CACHE_MAXSIZE: int = 1
    MEMORY_CACHE_TTL: int = 60

    # --- LibreOffice settings -----------------------------------------------
    LIBREOFFICE_BIN: str = "libreoffice"

    ##########################################################################
    # Database
    ##########################################################################
    ALEMBIC_INI_PATH: FilePath = PARENT / "alembic.ini"
    SQLALCHEMY_DATABASE_URI: str = "sqlite:////resources/cache/sqlite/database.db"

    ##########################################################################
    # ASR Config
    ##########################################################################
    TRANSCRIBE_WS_URI: str | None = None

    ##########################################################################
    # Disambiguation Config
    ##########################################################################
    # --- Fuzzy Matching -----------------------------------------------------
    THRESHOLD: int = 70

    # --- LLM ----------------------------------------------------------------
    MODEL: str = "phi4:14b"
    MODEL_CONTEXT: int = 9500
    TEMPERATURE: float = 0.0
    CONTEXT_WINDOW_LENGTH: int | None = 120
    TOKEN_LIMIT_FRAC: float = 2 / 3
    TOKENIZER_MODEL: str = "microsoft/phi-4"
    DECOMPOSE_BY: int | None = None

    # --- Label policies (JSON dict: label -> {disambiguation, anonymize}) ---
    DISAMBIGUATION_LABEL_POLICIES: dict | None = None

    # --- Render policy (JSON dict) ------------------------------------------
    RENDER_POLICY: dict | None = None

    @field_validator("DISAMBIGUATION_LABEL_POLICIES", "RENDER_POLICY", mode="before")
    @classmethod
    def parse_policies(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return json.loads(v)
        return v


load_env()
settings = Settings()
