import uuid
from unittest.mock import patch

import pytest

from aymurai.database.schema import (
    DataPublicDocument,
    DataPublicDocumentParagraph,
    DataPublicParagraph,
)
from aymurai.database.utils import text_to_uuid
from tests.api.conftest import build_label
from tests.api.routers.conftest import build_mock_pipeline


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.datapublic.datapublic.load_pipeline")
def test_should_return_prediction_when_valid_document_id_and_text(
    mock_load_pipeline, client
):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    document_id = uuid.uuid5(uuid.NAMESPACE_URL, "datapublic-predict-valid")
    response = client.post(
        f"/datapublic/predict/{document_id}",
        json={"text": "Sample datapublic text"},
        params={"use_cache": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert "document" in data
    assert "labels" in data
    assert data["document"] == "Sample datapublic text"
    assert isinstance(data["labels"], list)


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.datapublic.datapublic.load_pipeline")
def test_should_return_cached_prediction_when_text_in_cache(
    mock_load_pipeline, client, db_session
):
    text = "Cached datapublic text"
    labels = [build_label("PER", "Juan González").model_dump(mode="json")]

    paragraph_id = text_to_uuid(text)
    cached_para = DataPublicParagraph(
        id=paragraph_id,
        text=text,
        prediction=labels,
    )
    db_session.add(cached_para)
    db_session.commit()

    document_id = uuid.uuid5(uuid.NAMESPACE_URL, "datapublic-cached-text")
    response = client.post(
        f"/datapublic/predict/{document_id}",
        json={"text": text},
        params={"use_cache": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["document"] == text
    assert data["labels"] == labels
    mock_load_pipeline.assert_not_called()


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.datapublic.datapublic.load_pipeline")
def test_should_store_paragraph_and_document_when_use_cache_true(
    mock_load_pipeline, client, db_session
):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    document_id = uuid.uuid5(uuid.NAMESPACE_URL, "datapublic-store-cache-true")
    text = "New datapublic paragraph"

    response = client.post(
        f"/datapublic/predict/{document_id}",
        json={"text": text},
        params={"use_cache": True},
    )

    assert response.status_code == 200

    paragraph_id = text_to_uuid(text)
    stored_para = db_session.get(DataPublicParagraph, paragraph_id)
    assert stored_para is not None
    assert stored_para.text == text
    assert stored_para.prediction is not None

    stored_doc = db_session.get(DataPublicDocument, document_id)
    assert stored_doc is not None

    stored_link = (
        db_session.query(DataPublicDocumentParagraph)
        .filter_by(
            paragraph_id=paragraph_id,
            document_id=document_id,
        )
        .first()
    )
    assert stored_link is not None


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.datapublic.datapublic.load_pipeline")
def test_should_return_prediction_without_storing_when_use_cache_false(
    mock_load_pipeline, client, db_session
):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    document_id = uuid.uuid5(uuid.NAMESPACE_URL, "datapublic-cache-false")
    text = "No datapublic storage text"

    response = client.post(
        f"/datapublic/predict/{document_id}",
        json={"text": text},
        params={"use_cache": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert "document" in data
    assert "labels" in data

    paragraph_id = text_to_uuid(text)
    stored = db_session.get(DataPublicParagraph, paragraph_id)
    assert stored is None


@pytest.mark.integration
def test_should_return_422_when_document_id_not_uuid(client):
    response = client.post(
        "/datapublic/predict/not-a-uuid",
        json={"text": "Sample text"},
    )

    assert response.status_code == 422


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.datapublic.datapublic.load_pipeline")
def test_should_associate_multiple_paragraphs_with_same_document(
    mock_load_pipeline, client, db_session
):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    document_id = uuid.uuid5(uuid.NAMESPACE_URL, "datapublic-associate-paragraphs")
    text1 = "First paragraph for association"
    text2 = "Second paragraph for association"

    response1 = client.post(
        f"/datapublic/predict/{document_id}",
        json={"text": text1},
        params={"use_cache": True},
    )

    response2 = client.post(
        f"/datapublic/predict/{document_id}",
        json={"text": text2},
        params={"use_cache": True},
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    para1_id = text_to_uuid(text1)
    para2_id = text_to_uuid(text2)

    stored_doc = db_session.get(DataPublicDocument, document_id)
    assert stored_doc is not None

    links = (
        db_session.query(DataPublicDocumentParagraph)
        .filter_by(document_id=document_id)
        .all()
    )
    assert len(links) == 2

    link_para_ids = {link.paragraph_id for link in links}
    assert para1_id in link_para_ids
    assert para2_id in link_para_ids


@pytest.mark.integration
def test_should_return_404_when_validation_document_not_found(client):
    document_id = uuid.uuid5(uuid.NAMESPACE_URL, "datapublic-validation-missing")

    response = client.get(f"/datapublic/validation/document/{document_id}")

    assert response.status_code == 404


@pytest.mark.integration
def test_should_return_none_when_validation_not_set(client, db_session):
    document_id = uuid.uuid5(uuid.NAMESPACE_URL, "datapublic-validation-empty")
    db_session.add(DataPublicDocument(id=document_id))
    db_session.commit()

    response = client.get(f"/datapublic/validation/document/{document_id}")

    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.integration
def test_should_upsert_and_read_document_validation(client, db_session):
    document_id = uuid.uuid5(uuid.NAMESPACE_URL, "datapublic-validation-upsert")
    payload = {
        "materia": "penal",
        "violencia_de_genero": "si",
        "resolucion": {"tipo": "sentencia"},
    }

    post_response = client.post(
        f"/datapublic/validation/document/{document_id}",
        json=payload,
    )
    assert post_response.status_code == 200

    stored_doc = db_session.get(DataPublicDocument, document_id)
    assert stored_doc is not None
    assert stored_doc.validation == payload

    get_response = client.get(f"/datapublic/validation/document/{document_id}")
    assert get_response.status_code == 200
    assert get_response.json() == payload
