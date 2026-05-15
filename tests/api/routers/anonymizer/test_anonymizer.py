import base64
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from docx import Document

from aymurai.database.schema import AnonymizationParagraph
from aymurai.database.utils import text_to_uuid
from aymurai.text.anonymization import DocxAnonymizer, PdfAnonymizer, get_anonymizer
from aymurai.text.anonymization.alignment import index_paragraphs
from tests.api.conftest import build_label
from tests.api.routers.conftest import build_mock_pipeline

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6R8AAAAASUVORK5CYII="
)
WATERMARK_URL = "https://www.aymurai.info/"

WINDOWS_PYMUPDF_LAYOUT_XFAIL = pytest.mark.xfail(
    sys.platform == "win32",
    reason="pymupdf4llm ONNX layout model receives int32 tensors on Windows (expects int64)",
    strict=False,
)


def _write_pdf(path: Path, configure) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    configure(doc, page)
    doc.save(path)
    doc.close()
    return path


def _label_dict(text: str, label: str = "PER", **attrs) -> dict:
    payload = build_label(label, text).model_dump(mode="json")
    payload["attrs"].update(attrs)
    return payload


def _run_pdf_anonymizer(
    tmp_path: Path,
    source_path: Path,
    document: str,
    labels: list[dict],
) -> Path:
    output_dir = tmp_path / "out"
    output_dir.mkdir(exist_ok=True)
    output_path = PdfAnonymizer().anonymize(
        {"path": str(source_path)},
        [{"document": document, "labels": labels}],
        str(output_dir),
    )
    return Path(output_path)


@pytest.mark.integration
def test_anonymization_package_exports_and_registry_are_stable():
    assert PdfAnonymizer.__name__ == "PdfAnonymizer"
    assert DocxAnonymizer.__name__ == "DocxAnonymizer"
    assert isinstance(get_anonymizer("pdf"), PdfAnonymizer)
    assert isinstance(get_anonymizer("docx"), DocxAnonymizer)


@pytest.mark.integration
@WINDOWS_PYMUPDF_LAYOUT_XFAIL
def test_pdf_anonymizer_falls_back_from_invalid_alt_offsets(tmp_path):
    document = "Ana Perez firmo el escrito"
    source_path = _write_pdf(
        tmp_path / "invalid-alt.pdf",
        lambda _doc, page: page.insert_text((72, 72), document),
    )
    labels = [
        _label_dict(
            "Ana Perez",
            aymurai_alt_start_char=999,
            aymurai_alt_end_char=1000,
        )
    ]

    output_path = _run_pdf_anonymizer(tmp_path, source_path, document, labels)

    with pymupdf.open(output_path) as output_doc:
        page_text = output_doc[0].get_text()

    assert "Ana Perez" not in page_text
    assert "<PER>" in page_text


@pytest.mark.integration
@WINDOWS_PYMUPDF_LAYOUT_XFAIL
def test_pdf_anonymizer_scrubs_pdf_payloads_and_preserves_safe_links(tmp_path):
    document = "Ana Perez presento el escrito"

    def configure(doc: pymupdf.Document, page: pymupdf.Page) -> None:
        page.insert_text((72, 72), document)
        sensitive_rect = page.search_for("Ana Perez")[0]
        page.insert_link(
            {
                "kind": pymupdf.LINK_URI,
                "from": sensitive_rect,
                "uri": "https://secret.example",
            }
        )
        safe_rect = pymupdf.Rect(72, 140, 180, 155)
        page.insert_text((72, 150), "Portal publico")
        page.insert_link(
            {
                "kind": pymupdf.LINK_URI,
                "from": safe_rect,
                "uri": "https://safe.example",
            }
        )
        page.add_file_annot((220, 72), b"attached secret", "attached.txt")
        doc.set_metadata(
            {
                "title": "Secret title",
                "author": "Secret author",
                "subject": "Secret subject",
                "keywords": "alpha,beta",
                "creator": "Secret creator",
                "producer": "Secret producer",
            }
        )
        doc.set_xml_metadata("<x:xmpmeta>top-secret</x:xmpmeta>")
        doc.embfile_add("secret.txt", b"secret bytes", filename="secret.txt")

    source_path = _write_pdf(tmp_path / "metadata.pdf", configure)
    labels = [_label_dict("Ana Perez")]

    output_path = _run_pdf_anonymizer(tmp_path, source_path, document, labels)

    with pymupdf.open(output_path) as output_doc:
        page = output_doc[0]
        link_uris = {link.get("uri") for link in page.get_links()}

        assert output_doc.metadata.get("title") == ""
        assert output_doc.metadata.get("subject") == ""
        assert output_doc.metadata.get("keywords") == ""
        assert output_doc.metadata.get("creationDate") == ""
        assert re.fullmatch(
            r"D:\d{14}\+00'00'",
            output_doc.metadata.get("modDate") or "",
        )
        assert output_doc.metadata.get("trapped") == ""
        assert output_doc.metadata.get("author") == ""
        assert output_doc.metadata.get("creator") == "AymurAI"
        assert output_doc.metadata.get("producer") == "AymurAI"
        assert not output_doc.get_xml_metadata()
        assert output_doc.embfile_names() == []
        assert list(page.annots() or []) == []
        assert "https://secret.example" not in link_uris
        assert "https://safe.example" in link_uris
        assert WATERMARK_URL in link_uris


@pytest.mark.integration
@WINDOWS_PYMUPDF_LAYOUT_XFAIL
def test_pdf_anonymizer_moves_watermark_away_from_footer_content(tmp_path):
    document = "Ana Perez presento el escrito"
    footer_rect = pymupdf.Rect(360, 760, 575, 815)

    def configure(_doc: pymupdf.Document, page: pymupdf.Page) -> None:
        page.insert_text((72, 72), document)
        page.draw_rect(footer_rect, color=(0, 0, 0), fill=(0, 0, 0), overlay=True)

    source_path = _write_pdf(tmp_path / "footer-watermark.pdf", configure)
    output_path = _run_pdf_anonymizer(
        tmp_path,
        source_path,
        document,
        [_label_dict("Ana Perez")],
    )

    with pymupdf.open(output_path) as output_doc:
        page = output_doc[0]
        watermark_links = [
            link for link in page.get_links() if link.get("uri") == WATERMARK_URL
        ]

        assert len(watermark_links) == 1
        watermark_rect = pymupdf.Rect(watermark_links[0]["from"])
        assert not watermark_rect.intersects(footer_rect)
        assert watermark_rect.x1 < footer_rect.x0


@pytest.mark.integration
@WINDOWS_PYMUPDF_LAYOUT_XFAIL
def test_pdf_anonymizer_removes_image_backed_entities(tmp_path):
    source_path = _write_pdf(
        tmp_path / "image.pdf",
        lambda _doc, page: (
            page.insert_image(pymupdf.Rect(60, 60, 220, 110), stream=PNG_1X1),
            page.insert_text((80, 90), "Ana Perez"),
        ),
    )

    output_path = _run_pdf_anonymizer(
        tmp_path,
        source_path,
        "Ana Perez",
        [_label_dict("Ana Perez")],
    )

    with pymupdf.open(output_path) as output_doc:
        page = output_doc[0]
        page_text = page.get_text()

        assert page.get_image_info() == []
        assert "Ana Perez" not in page_text
        assert "<PER>" in page_text


@pytest.mark.integration
@WINDOWS_PYMUPDF_LAYOUT_XFAIL
def test_pdf_anonymizer_removes_signature_widgets_without_restoring_appearance(
    tmp_path,
):
    def configure(_doc: pymupdf.Document, page: pymupdf.Page) -> None:
        page.insert_text((80, 90), "Ana Perez")
        widget = pymupdf.Widget()
        widget.field_name = "sig_1"
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
        widget.rect = pymupdf.Rect(60, 60, 220, 110)
        page.add_widget(widget)

    source_path = _write_pdf(tmp_path / "signature.pdf", configure)
    output_path = _run_pdf_anonymizer(
        tmp_path,
        source_path,
        "Ana Perez",
        [_label_dict("Ana Perez")],
    )

    with pymupdf.open(output_path) as output_doc:
        page = output_doc[0]
        page_text = page.get_text()

        assert list(page.widgets() or []) == []
        assert page.get_image_info() == []
        assert "Ana Perez" not in page_text
        assert "<PER>" in page_text


def test_index_paragraphs_reads_docx_xml_as_utf8(tmp_path):
    xml_path = tmp_path / "document.xml"
    xml_path.write_bytes(
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>Señora — resolución</w:t></w:r></w:p>
  </w:body>
</w:document>
""".encode("utf-8")
    )

    paragraphs = index_paragraphs(str(xml_path))

    assert len(paragraphs) == 1
    assert paragraphs[0]["plain_text"] == "Señora — resolución"


@pytest.mark.integration
def test_docx_anonymizer_sets_aymurai_core_properties(tmp_path):
    source_path = tmp_path / "source.docx"
    document = Document()
    document.add_paragraph("Ana Perez firmo el escrito")
    document.core_properties.author = "Sensitive Author"
    document.core_properties.last_modified_by = "Sensitive Modifier"
    document.save(source_path)

    started_at = datetime.now(timezone.utc).replace(microsecond=0)

    output_path = DocxAnonymizer().anonymize(
        {"path": str(source_path)},
        [
            {
                "document": "Ana Perez firmo el escrito",
                "labels": [_label_dict("Ana Perez")],
            }
        ],
        str(tmp_path / "out"),
    )

    output_document = Document(output_path)
    core_properties = output_document.core_properties
    assert core_properties.author == ""
    assert core_properties.last_modified_by == "AymurAI"
    assert core_properties.modified is not None
    modified = core_properties.modified
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=timezone.utc)
    assert started_at <= modified <= datetime.now(timezone.utc) + timedelta(seconds=5)


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
def test_should_return_prediction_when_text_provided(mock_load_pipeline, client):
    mock_pipeline = build_mock_pipeline()
    mock_load_pipeline.return_value = mock_pipeline

    response = client.post(
        "/api/anonymizer/predict",
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
        "/api/anonymizer/predict",
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
        "/api/anonymizer/predict",
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
        "/api/anonymizer/predict",
        json={"text": text},
        params={"use_cache": True},
    )
    data1 = response1.json()

    response2 = client.post(
        "/api/anonymizer/predict",
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
        "/api/anonymizer/predict",
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
        "/api/anonymizer/predict",
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
        "/api/anonymizer/predict",
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
        "/api/anonymizer/predict",
        json={"text": text1},
        params={"use_cache": True},
    )

    response2 = client.post(
        "/api/anonymizer/predict",
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


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.load_pipeline")
def test_should_dedupe_duplicate_labels_when_returning_cached_prediction(
    mock_load_pipeline, client, db_session
):
    text = "EL SEÑOR JUEZ, doctor Tarte, señaló :"
    label = build_label("PER", "Tarte").model_dump(mode="json")
    label.update({"start_char": 22, "end_char": 27})
    label["attrs"].update(
        {
            "aymurai_alt_text": "Tarte",
            "aymurai_alt_start_char": 22,
            "aymurai_alt_end_char": 27,
            "aymurai_disambiguation": "fuzzy",
            "aymurai_anonymize": True,
        }
    )

    db_session.add(
        AnonymizationParagraph(
            id=text_to_uuid(text),
            text=text,
            prediction=[label, label],
        )
    )
    db_session.commit()

    response = client.post(
        "/api/anonymizer/predict",
        json={"text": text},
        params={"use_cache": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["document"] == text
    assert data["labels"] == [label]
    mock_load_pipeline.assert_not_called()


@pytest.mark.integration
@patch(
    "aymurai.api.endpoints.routers.anonymizer.anonymizer.map_canonical_entities_ner_preds"
)
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.get_canonical_dates")
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.build_canonical_entities")
def test_should_disambiguate_and_persist_paragraphs(
    mock_build_canonical_entities,
    mock_get_canonical_dates,
    mock_map_canonical_entities,
    client,
    db_session,
):
    mock_build_canonical_entities.return_value = []
    mock_get_canonical_dates.return_value = []
    mock_map_canonical_entities.side_effect = lambda predictions, canonical_entities: (
        predictions
    )

    text = "Ana Pérez denunció en el juzgado."
    body = {
        "paragraphs": [
            {
                "document": text,
                "labels": [build_label("PER", "Ana Pérez").model_dump(mode="json")],
            }
        ],
        "label_policies": {
            "PER": {"anonymize": True, "disambiguation": "none"},
        },
    }

    response = client.post("/api/anonymizer/disambiguate", json=body)

    assert response.status_code == 200
    payload = response.json()
    assert payload["label_policies"]["PER"]["disambiguation"] == "none"
    assert payload["data"][0]["labels"][0]["attrs"]["aymurai_disambiguation"] == "none"
    assert payload["data"][0]["labels"][0]["attrs"]["aymurai_anonymize"] is True

    paragraph_id = text_to_uuid(text)
    stored = db_session.get(AnonymizationParagraph, paragraph_id)
    assert stored is not None
    assert stored.prediction is not None
    assert stored.prediction[0]["text"] == "Ana Pérez"


@pytest.mark.integration
@patch(
    "aymurai.api.endpoints.routers.anonymizer.anonymizer.map_canonical_entities_ner_preds"
)
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.get_canonical_dates")
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.build_canonical_entities")
def test_should_dedupe_duplicate_labels_when_disambiguating_and_persisting(
    mock_build_canonical_entities,
    mock_get_canonical_dates,
    mock_map_canonical_entities,
    client,
    db_session,
):
    mock_build_canonical_entities.return_value = []
    mock_get_canonical_dates.return_value = []
    mock_map_canonical_entities.side_effect = lambda predictions, canonical_entities: (
        predictions
    )

    text = "EL SEÑOR JUEZ, doctor Tarte, señaló :"
    label = build_label("PER", "Tarte").model_dump(mode="json")
    label.update({"start_char": 22, "end_char": 27})
    label["attrs"].update(
        {
            "aymurai_alt_text": "Tarte",
            "aymurai_alt_start_char": 22,
            "aymurai_alt_end_char": 27,
        }
    )
    body = {
        "paragraphs": [{"document": text, "labels": [label, label]}],
        "label_policies": {
            "PER": {"anonymize": True, "disambiguation": "none"},
        },
    }

    response = client.post("/api/anonymizer/disambiguate", json=body)

    assert response.status_code == 200
    labels = response.json()["data"][0]["labels"]
    assert labels == [
        {
            **label,
            "attrs": {
                **label["attrs"],
                "aymurai_disambiguation": "none",
                "aymurai_anonymize": True,
            },
        }
    ]

    stored = db_session.get(AnonymizationParagraph, text_to_uuid(text))
    assert stored is not None
    assert stored.prediction is not None
    assert len(stored.prediction) == 1
    assert stored.prediction[0]["text"] == "Tarte"
    assert stored.prediction[0]["attrs"]["aymurai_disambiguation"] == "none"
    assert stored.prediction[0]["attrs"]["aymurai_anonymize"] is True


@pytest.mark.integration
def test_should_return_null_validation_when_paragraph_not_found(client):
    response = client.post(
        "/api/anonymizer/validation",
        json={"text": "Paragraph without validation"},
    )

    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.integration
def test_should_return_validation_when_paragraph_exists(client, db_session):
    text = "Validated paragraph"
    labels = [build_label("PER", "María Soto").model_dump(mode="json")]
    db_session.add(
        AnonymizationParagraph(
            id=text_to_uuid(text),
            text=text,
            validation=labels,
        )
    )
    db_session.commit()

    response = client.post("/api/anonymizer/validation", json={"text": text})

    assert response.status_code == 200
    assert response.json() == labels


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.get_anonymizer")
def test_should_return_application_pdf_when_pdf_document_is_anonymized(
    mock_get_anonymizer,
    client,
    tmp_path,
):
    anonymized_path = _write_pdf(
        tmp_path / "output.pdf",
        lambda _doc, page: page.insert_text((72, 72), "Anonymized PDF output"),
    )
    mock_get_anonymizer.return_value = MagicMock(return_value=str(anonymized_path))

    annotations = {
        "data": [
            {
                "document": "Ana Perez presento el escrito",
                "labels": [build_label("PER", "Ana Perez").model_dump(mode="json")],
            }
        ],
        "label_policies": {"PER": {"anonymize": True, "disambiguation": "none"}},
        "render_policy": {"suffix_mode": "auto", "suffix_threshold": 1},
    }

    response = client.post(
        "/api/anonymizer/anonymize-document",
        data={"annotations": json.dumps(annotations)},
        files={"file": ("sample.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 0


@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.subprocess.check_output")
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.get_anonymizer")
def test_should_anonymize_document_when_annotations_are_valid(
    mock_get_anonymizer, mock_check_output, client, tmp_path
):
    # Fake anonymizer that writes a dummy docx output
    anonymized_path = str(tmp_path / "output.docx")
    with open(anonymized_path, "wb") as f:
        f.write(b"fake-docx-content")

    mock_anonymizer = MagicMock(return_value=anonymized_path)
    mock_get_anonymizer.return_value = mock_anonymizer

    def fake_convert(*args, **kwargs):
        cmd = args[0]
        source_path = cmd[-1]
        output_path = source_path.rsplit(".", 1)[0] + ".odt"
        with open(output_path, "wb") as output_file:
            output_file.write(b"odt-content")
        return "ok"

    mock_check_output.side_effect = fake_convert
    annotations = {
        "data": [
            {
                "document": "Ana Pérez denunció en el juzgado.",
                "labels": [build_label("PER", "Ana Pérez").model_dump(mode="json")],
            }
        ],
        "label_policies": {"PER": {"anonymize": True, "disambiguation": "fuzzy"}},
        "render_policy": {"suffix_mode": "auto", "suffix_threshold": 1},
    }

    response = client.post(
        "/api/anonymizer/anonymize-document",
        data={"annotations": json.dumps(annotations)},
        files={
            "file": (
                "sample.docx",
                b"input-document",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert len(response.content) > 0


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.subprocess.check_output")
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.get_anonymizer")
def test_should_exclude_null_alt_attrs_from_anonymize_document_preds(
    mock_get_anonymizer, mock_check_output, client, tmp_path
):
    anonymized_path = str(tmp_path / "output.docx")
    with open(anonymized_path, "wb") as f:
        f.write(b"fake-docx-content")

    mock_anonymizer = MagicMock(return_value=anonymized_path)
    mock_get_anonymizer.return_value = mock_anonymizer

    def fake_convert(*args, **kwargs):
        cmd = args[0]
        source_path = cmd[-1]
        output_path = source_path.rsplit(".", 1)[0] + ".odt"
        with open(output_path, "wb") as output_file:
            output_file.write(b"odt-content")
        return "ok"

    mock_check_output.side_effect = fake_convert
    annotations = {
        "data": [
            {
                "document": "Ana Perez denuncio en el juzgado.",
                "labels": [build_label("PER", "Ana Perez").model_dump(mode="json")],
            }
        ],
        "label_policies": {"PER": {"anonymize": True, "disambiguation": "fuzzy"}},
        "render_policy": {"suffix_mode": "auto", "suffix_threshold": 1},
    }

    response = client.post(
        "/api/anonymizer/anonymize-document",
        data={"annotations": json.dumps(annotations)},
        files={
            "file": (
                "sample.docx",
                b"input-document",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    preds = mock_anonymizer.call_args[0][1]
    assert preds[0]["labels"][0]["text"] == "Ana Perez"

    attrs = preds[0]["labels"][0]["attrs"]
    assert "aymurai_alt_text" not in attrs
    assert "aymurai_alt_start_char" not in attrs
    assert "aymurai_alt_end_char" not in attrs


@pytest.mark.integration
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.subprocess.check_output")
@patch("aymurai.api.endpoints.routers.anonymizer.anonymizer.get_anonymizer")
def test_should_return_500_when_anonymize_document_conversion_fails(
    mock_get_anonymizer, mock_check_output, client, tmp_path
):
    # Fake anonymizer that writes a dummy output
    anonymized_path = str(tmp_path / "output.docx")
    with open(anonymized_path, "wb") as f:
        f.write(b"fake-docx-content")

    mock_anonymizer = MagicMock(return_value=anonymized_path)
    mock_get_anonymizer.return_value = mock_anonymizer

    mock_check_output.side_effect = subprocess.CalledProcessError(
        1,
        ["libreoffice"],
        output=b"conversion failed",
    )
    annotations = {
        "data": [{"document": "text", "labels": []}],
        "label_policies": None,
        "render_policy": {"suffix_mode": "auto", "suffix_threshold": 1},
    }

    response = client.post(
        "/api/anonymizer/anonymize-document",
        data={"annotations": json.dumps(annotations)},
        files={
            "file": (
                "sample.docx",
                b"input-document",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 500
