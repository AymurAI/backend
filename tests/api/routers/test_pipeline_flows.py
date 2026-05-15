import io
import json
import shutil
import uuid
from unittest.mock import MagicMock, patch

import pytest
from docx import Document as DocxDocument

from aymurai.database.schema import DataPublicDocumentParagraph
from tests.api.routers.conftest import build_mock_pipeline


def _fake_libreoffice_convert(*args, **kwargs):
    cmd = args[0]
    source_path = cmd[-1]
    output_path = source_path.rsplit(".", 1)[0] + ".odt"
    with open(output_path, "wb") as output_file:
        output_file.write(b"odt-content")
    return "ok"


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.subprocess.check_output")
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.get_anonymizer")
@patch(
    "aymurai.api.endpoints.routers.anonymizer.anonymizer.map_canonical_entities_ner_preds"
)
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.get_canonical_dates")
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.build_canonical_entities")
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_run_anonymizer_flow_end_to_end(
    mock_extract,
    mock_load_pipeline,
    mock_build_canonical_entities,
    mock_get_canonical_dates,
    mock_map_canonical_entities,
    mock_get_anonymizer,
    mock_check_output,
    client,
    tmp_path,
):
    mock_extract.return_value = "Ana Pérez denunció.\nJuan Soto declaró."
    mock_load_pipeline.return_value = build_mock_pipeline()
    mock_build_canonical_entities.return_value = []
    mock_get_canonical_dates.return_value = []
    mock_map_canonical_entities.side_effect = lambda predictions, canonical_entities: (
        predictions
    )

    anonymized_path = str(tmp_path / "output.docx")
    with open(anonymized_path, "wb") as f:
        f.write(b"fake-docx-content")
    mock_anonymizer = MagicMock(return_value=anonymized_path)
    mock_get_anonymizer.return_value = mock_anonymizer
    mock_check_output.side_effect = _fake_libreoffice_convert

    extract_response = client.post(
        "/api/misc/document-extract",
        files={
            "file": (
                "sample.docx",
                b"doc-bytes",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert extract_response.status_code == 200
    paragraphs = extract_response.json()["document"]
    assert len(paragraphs) == 2

    predictions = []
    for paragraph in paragraphs:
        predict_response = client.post(
            "/api/anonymizer/predict", json={"text": paragraph}
        )
        assert predict_response.status_code == 200
        predictions.append(predict_response.json())

    disambiguate_response = client.post(
        "/api/anonymizer/disambiguate",
        json={
            "paragraphs": predictions,
            "label_policies": {
                "PER": {"anonymize": True, "disambiguation": "fuzzy"},
            },
        },
    )
    assert disambiguate_response.status_code == 200
    annotations = disambiguate_response.json()
    assert len(annotations["data"]) == len(paragraphs)

    compile_response = client.post(
        "/api/anonymizer/anonymize-document",
        data={"annotations": json.dumps(annotations)},
        files={
            "file": (
                "sample.docx",
                b"doc-bytes",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert compile_response.status_code == 200
    assert compile_response.headers["content-type"] == "application/octet-stream"

    validation_response = client.post(
        "/api/anonymizer/validation",
        json={"text": paragraphs[0]},
    )
    assert validation_response.status_code == 200
    assert isinstance(validation_response.json(), list)


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.datapublic.datapublic.load_pipeline")
@patch("aymurai.api.endpoints.routers.misc.document_extract.run_safe_text_extraction")
def test_should_run_datapublic_flow_end_to_end(
    mock_extract,
    mock_load_pipeline,
    client,
    db_session,
):
    mock_extract.return_value = "Primera oración.\nSegunda oración."
    mock_load_pipeline.return_value = build_mock_pipeline()

    extract_response = client.post(
        "/api/misc/document-extract",
        files={
            "file": (
                "sample.docx",
                b"doc-bytes",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert extract_response.status_code == 200
    paragraphs = extract_response.json()["document"]
    assert len(paragraphs) == 2

    document_id = uuid.uuid5(uuid.NAMESPACE_URL, "datapublic-e2e-flow")
    for paragraph in paragraphs:
        predict_response = client.post(
            f"/api/datapublic/predict/{document_id}",
            json={"text": paragraph},
        )
        assert predict_response.status_code == 200

    links = (
        db_session.query(DataPublicDocumentParagraph)
        .filter_by(document_id=document_id)
        .all()
    )
    assert len(links) == len(paragraphs)

    validation_payload = {"materia": "penal", "violencia_de_genero": "si"}
    save_response = client.post(
        f"/api/datapublic/validation/document/{document_id}",
        json=validation_payload,
    )
    assert save_response.status_code == 200

    read_response = client.get(f"/api/datapublic/validation/document/{document_id}")
    assert read_response.status_code == 200
    assert read_response.json() == validation_payload


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.external
def test_should_compile_anonymized_document_with_real_libreoffice_when_available(
    client,
):
    if shutil.which("libreoffice") is None:
        pytest.skip("LibreOffice binary is required for real compile integration test")

    annotations = {
        "data": [{"document": "Texto base para anonimizar.", "labels": []}],
        "label_policies": None,
        "render_policy": {"suffix_mode": "auto", "suffix_threshold": 1},
    }

    doc = DocxDocument()
    doc.add_paragraph("Texto base para anonimizar.")
    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    response = client.post(
        "/api/anonymizer/anonymize-document",
        data={"annotations": json.dumps(annotations)},
        files={
            "file": (
                "sample.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
