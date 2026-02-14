from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, StaticPool, create_engine

from aymurai.api.main import api
from aymurai.database.meta.anonymization.paragraph import AnonymizationParagraphCreate
from aymurai.database.meta.datapublic.paragraph import DataPublicParagraphCreate
from aymurai.database.session import get_session
from aymurai.database.utils import text_to_uuid
from aymurai.meta.api_interfaces import DocLabel
from aymurai.meta.entities import EntityAttributes


@pytest.fixture(scope="session")
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
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_session():
        return db_session

    api.dependency_overrides[get_session] = override_get_session

    with TestClient(api, raise_server_exceptions=False) as c:
        yield c

    api.dependency_overrides.clear()


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
