import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from aymurai.api.endpoints.routers.anonymizer import anonymizer
from aymurai.api.endpoints.routers.asr import transcribe
from aymurai.api.exceptions.handlers import register_exceptions_handlers
from aymurai.database.session import get_session

INTEGRATION_AUDIO_URL = (
    "https://google-research.github.io/lingvo-lab/translatotron/fisher_src/775.wav"
)


@pytest.fixture
def integration_api_client(sqlite_engine):
    app = FastAPI()
    register_exceptions_handlers(app)
    app.include_router(transcribe.router, prefix="/asr")
    app.include_router(anonymizer.router, prefix="/anonymizer")

    def _override_get_session():
        with Session(sqlite_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session

    with TestClient(app) as client:
        yield client


@pytest.fixture
def integration_audio_bytes() -> bytes:
    response = requests.get(INTEGRATION_AUDIO_URL, timeout=30)
    response.raise_for_status()
    return response.content
