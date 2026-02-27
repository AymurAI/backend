import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from aymurai.api.endpoints.routers.asr import transcribe
from aymurai.api.exceptions.handlers import register_exceptions_handlers
from aymurai.database.session import get_session
from aymurai.settings import settings


@pytest.fixture
def asr_test_client(sqlite_engine):
    app = FastAPI()
    register_exceptions_handlers(app)
    app.include_router(transcribe.router, prefix="/asr")

    def _override_get_session():
        with Session(sqlite_engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    original_ws_uri = settings.TRANSCRIBE_WS_URI
    settings.TRANSCRIBE_WS_URI = "ws://test-transcribe.local/ws"

    with TestClient(app) as client:
        yield client, sqlite_engine

    settings.TRANSCRIBE_WS_URI = original_ws_uri
