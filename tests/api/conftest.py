import os
from pathlib import Path

import diskcache
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, StaticPool, create_engine

os.environ.setdefault("DISKCACHE_ROOT", "/tmp/aymurai-test-diskcache")
os.environ.setdefault("AYMURAI_CACHE_BASEPATH", "/tmp/aymurai-test-cache")
os.environ.setdefault("RESOURCES_BASEPATH", "resources")

from aymurai.api.endpoints.routers.anonymizer import anonymizer
from aymurai.api.endpoints.routers.datapublic import datapublic
from aymurai.api.endpoints.routers.misc import document_extract
from aymurai.database.meta.anonymization.paragraph import AnonymizationParagraphCreate
from aymurai.database.meta.datapublic.paragraph import DataPublicParagraphCreate
from aymurai.database.session import get_session
from aymurai.database.utils import text_to_uuid
from aymurai.meta.api_interfaces import DocLabel
from aymurai.meta.entities import EntityAttributes


@pytest.fixture(scope="function")
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(
        anonymizer.router,
        prefix="/anonymizer",
        tags=["anonymization/model"],
    )
    test_app.include_router(
        datapublic.router,
        prefix="/datapublic",
        tags=["datapublic/model"],
    )
    test_app.include_router(document_extract.router, tags=["document"], deprecated=True)
    test_app.include_router(document_extract.router, prefix="/misc", tags=["document"])
    return test_app


@pytest.fixture(scope="function", autouse=True)
def isolated_diskcache(tmp_path):
    from aymurai.utils import cache as cache_module

    original_cache = cache_module.cache
    test_cache = diskcache.Cache(str(tmp_path / "diskcache"))
    cache_module.cache = test_cache
    try:
        yield test_cache
    finally:
        cache_module.cache = original_cache
        test_cache.close()


@pytest.fixture(scope="function")
def db_engine():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)

    return test_engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    session = Session(db_engine)
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(app, db_engine):
    def override_get_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    c = TestClient(app, raise_server_exceptions=False)
    try:
        yield c
    finally:
        c.close()
        app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def sample_docx():
    return Path("test/api/test_file.docx")


def build_data_item(text: str = "sample text") -> dict:
    return {
        "path": "test",
        "extension": "docx",
        "dataset": "test",
        "data": {"doc.text": text},
        "annotations": None,
        "predictions": None,
    }


def build_label(label: str = "PER", value: str = "John Doe") -> DocLabel:
    attrs = EntityAttributes(aymurai_label=label)
    return DocLabel(
        text=value,
        start_char=0,
        end_char=len(value),
        attrs=attrs,
    )


def build_anonymization_paragraph(
    text: str = "sample text",
    prediction: list[DocLabel] | None = None,
    validation: list[DocLabel] | None = None,
) -> AnonymizationParagraphCreate:
    return AnonymizationParagraphCreate(
        id=text_to_uuid(text),
        text=text,
        prediction=prediction,
        validation=validation,
    )


def build_datapublic_paragraph(
    text: str = "sample text",
    prediction: list[DocLabel] | None = None,
    validation: list[DocLabel] | None = None,
) -> DataPublicParagraphCreate:
    return DataPublicParagraphCreate(
        id=text_to_uuid(text),
        text=text,
        prediction=prediction,
        validation=validation,
    )
