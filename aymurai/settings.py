import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import ConfigDict, FilePath, field_validator
from pydantic_settings import BaseSettings
from aymurai.logger import get_logger
import aymurai

try:
    from aymurai.version import __version__
except ImportError:
    __version__ = "0.0.0"

PARENT = Path(aymurai.__file__).parent

logger = get_logger(__name__)


def load_env():
    logger.info("Loading environment variables from .env files")
    load_dotenv(".env")

    # Load the stage-specific .env file (if it exists)
    stage = os.getenv("STAGE")
    if stage:
        logger.info(f"Loading environment variables for stage: {stage}")
        env_file = f".env.{stage}"
        if os.path.exists(env_file):
            logger.info(f"Loading environment variables from {env_file}")
            load_dotenv(env_file)


class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True)

    APP_VERSION: str = __version__

    ERROR_HANDLER: Literal["ignore", "raise"] = "ignore"

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

    # ----- Miscellaneous settings -----
    SWAGGER_UI_DARK_MODE: bool = False
    DEVELOPMENT_MODE: bool = False


load_env()
settings = Settings()
