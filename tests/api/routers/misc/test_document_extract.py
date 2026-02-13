import concurrent.futures
import uuid
from unittest.mock import patch

import pytest


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_return_document_with_paragraphs_when_uploading_docx(
    mock_extraction, client
):
    """Test that document extraction returns paragraphs in response."""
    mock_extraction.return_value = "Para 1\nPara 2\nPara 3"

    files = {
        "file": (
            "test.docx",
            b"test content",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = client.post("/document-extract", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "document" in data
    assert "document_id" in data
    assert isinstance(data["document"], list)
    assert len(data["document"]) == 3
    assert data["document"] == ["Para 1", "Para 2", "Para 3"]


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_return_document_via_misc_prefix_when_uploading(mock_extraction, client):
    """Test that /misc/document-extract endpoint works."""
    mock_extraction.return_value = "Sample text"

    files = {
        "file": (
            "test.docx",
            b"content",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = client.post("/document-extract", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["document"] == ["Sample text"]


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_return_deterministic_id_when_uploading_same_file_twice(
    mock_extraction, client
):
    """Test that same file bytes produce same document_id."""
    mock_extraction.return_value = "Same content"

    file_content = b"identical content"
    files = {
        "file": (
            "test.docx",
            file_content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    response1 = client.post("/document-extract", files=files)
    data1 = response1.json()

    # Reset mock and upload same file again
    response2 = client.post("/document-extract", files=files)
    data2 = response2.json()

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert data1["document_id"] == data2["document_id"]


@pytest.mark.integration
def test_should_return_422_when_no_file_provided(client):
    """Test that missing file returns 422 Unprocessable Entity."""
    response = client.post("/document-extract", files={})

    assert response.status_code == 422


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_return_empty_document_when_file_is_empty(mock_extraction, client):
    """Test that empty extraction returns empty document list."""
    mock_extraction.return_value = ""

    files = {
        "file": (
            "test.docx",
            b"content",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = client.post("/document-extract", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["document"] == []


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_collapse_consecutive_duplicates_when_extracting(
    mock_extraction, client
):
    """Test that consecutive duplicate paragraphs are collapsed."""
    mock_extraction.return_value = "A\nA\nB\nB\nB\nC"

    files = {
        "file": (
            "test.docx",
            b"content",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = client.post("/document-extract", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["document"] == ["A", "B", "C"]


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_normalize_whitespace_when_extracting(mock_extraction, client):
    """Test that multiple spaces are normalized to single space."""
    mock_extraction.return_value = "word1  word2   word3"

    files = {
        "file": (
            "test.docx",
            b"content",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = client.post("/document-extract", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["document"] == ["word1 word2 word3"]


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_return_504_when_extraction_times_out(mock_extraction, client):
    """Test that TimeoutError returns 504 Gateway Timeout."""
    mock_extraction.side_effect = concurrent.futures.TimeoutError()

    files = {
        "file": (
            "test.docx",
            b"content",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = client.post("/document-extract", files=files)

    assert response.status_code == 504


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_return_500_when_extraction_fails(mock_extraction, client):
    """Test that extraction errors return 500 Internal Server Error."""
    mock_extraction.side_effect = Exception("Extraction failed")

    files = {
        "file": (
            "test.docx",
            b"content",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    response = client.post("/document-extract", files=files)

    assert response.status_code == 500
