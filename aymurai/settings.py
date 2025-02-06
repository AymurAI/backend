import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_core import MultiHostUrl
from typing_extensions import Annotated
from pydantic_settings import BaseSettings
from pydantic import FilePath, ConfigDict, UrlConstraints, field_validator

import aymurai

PARENT = Path(aymurai.__file__).parent

SQLiteDNS = Annotated[
    MultiHostUrl,
    UrlConstraints(host_required=False, allowed_schemes=["sqlite"]),
]


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

    SQLALCHEMY_DATABASE_URI: SQLiteDNS = "sqlite:////resources/cache/sqlite/database.db"

    RESOURCES_BASEPATH: str = "/resources"

    # Alembic Config for running migrations
    ALEMBIC_INI_PATH: FilePath = PARENT / "alembic.ini"

    ENV: str | None = None

    # Cachetools settings
    MEMORY_CACHE_MAXSIZE: int = 1
    MEMORY_CACHE_TTL: int = 60

    LIBREOFFICE_BIN: str = "libreoffice"


load_env()
settings = Settings()
