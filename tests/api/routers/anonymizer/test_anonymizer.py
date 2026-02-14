from unittest.mock import patch

import pytest

from aymurai.database.schema import AnonymizationParagraph
from aymurai.database.utils import text_to_uuid
from tests.api.conftest import build_label
from tests.api.routers.conftest import build_mock_pipeline


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
def test_should_return_prediction_when_text_provided(mock_load_pipeline, client):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    response = client.post(
        "/anonymizer/predict",
        json={"text": "Sample anonymization text"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "document" in data
    assert "labels" in data
    assert data["document"] == "Sample anonymization text"
    assert isinstance(data["labels"], list)


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
def test_should_return_cached_prediction_when_text_in_cache(
    mock_load_pipeline, client, db_session
):
    text = "Cached text with entities"
    labels = [build_label("PER", "Juan Pérez").model_dump(mode="json")]

    paragraph_id = text_to_uuid(text)
    cached_para = AnonymizationParagraph(
        id=paragraph_id,
        text=text,
        prediction=labels,
    )
    db_session.add(cached_para)
    db_session.commit()

    response = client.post(
        "/anonymizer/predict",
        json={"text": text},
        params={"use_cache": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["document"] == text
    assert data["labels"] == labels
    mock_load_pipeline.assert_not_called()


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
def test_should_store_prediction_in_db_when_use_cache_true(
    mock_load_pipeline, client, db_session
):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    text = "New prediction to cache"
    response = client.post(
        "/anonymizer/predict",
        json={"text": text},
        params={"use_cache": True},
    )

    assert response.status_code == 200

    paragraph_id = text_to_uuid(text)
    stored = db_session.get(AnonymizationParagraph, paragraph_id)
    assert stored is not None
    assert stored.text == text
    assert stored.prediction is not None


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
def test_should_return_cached_result_when_calling_twice(mock_load_pipeline, client):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    text = "Repeated query text"

    response1 = client.post(
        "/anonymizer/predict",
        json={"text": text},
        params={"use_cache": True},
    )
    data1 = response1.json()

    response2 = client.post(
        "/anonymizer/predict",
        json={"text": text},
        params={"use_cache": True},
    )
    data2 = response2.json()

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert data1["document"] == data2["document"]
    assert data1["labels"] == data2["labels"]


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
def test_should_return_prediction_without_storing_when_use_cache_false(
    mock_load_pipeline, client, db_session
):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    text = "No cache storage text"
    response = client.post(
        "/anonymizer/predict",
        json={"text": text},
        params={"use_cache": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert "document" in data
    assert "labels" in data

    paragraph_id = text_to_uuid(text)
    stored = db_session.get(AnonymizationParagraph, paragraph_id)
    assert stored is None


@pytest.mark.integration
def test_should_return_422_when_payload_is_invalid_json(client):
    response = client.post(
        "/anonymizer/predict",
        content="not json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
def test_should_use_cache_by_default_when_param_omitted(
    mock_load_pipeline, client, db_session
):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    text = "Default cache behavior"
    response = client.post(
        "/anonymizer/predict",
        json={"text": text},
    )

    assert response.status_code == 200

    paragraph_id = text_to_uuid(text)
    stored = db_session.get(AnonymizationParagraph, paragraph_id)
    assert stored is not None
    assert stored.text == text


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
def test_should_isolate_cache_when_different_texts(
    mock_load_pipeline, client, db_session
):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    text1 = "First text for cache"
    text2 = "Second text for cache"

    para1_id = text_to_uuid(text1)
    para2_id = text_to_uuid(text2)

    labels1 = [build_label("PER", "Person1").model_dump(mode="json")]
    labels2 = [build_label("LOC", "Location1").model_dump(mode="json")]

    para1 = AnonymizationParagraph(id=para1_id, text=text1, prediction=labels1)
    para2 = AnonymizationParagraph(id=para2_id, text=text2, prediction=labels2)

    db_session.add_all([para1, para2])
    db_session.commit()

    response1 = client.post(
        "/anonymizer/predict",
        json={"text": text1},
        params={"use_cache": True},
    )

    response2 = client.post(
        "/anonymizer/predict",
        json={"text": text2},
        params={"use_cache": True},
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    assert data1["labels"] == labels1
    assert data2["labels"] == labels2
    assert data1["labels"] != data2["labels"]
