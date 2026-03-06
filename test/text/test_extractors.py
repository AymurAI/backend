from pathlib import Path
from unittest.mock import patch

import pytest

from aymurai.text.extractors.base import InvalidFile
from aymurai.text.extractors.docx import DocxExtractor
from aymurai.text.extractors.odt import OdtExtractor
from aymurai.text.extractors.pdf import PdfExtractor


def test_docx_extractor_appends_footnotes(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.docx"
    file_path.write_bytes(b"fake docx content")

    with (
        patch(
            "aymurai.text.extractors.docx.docx2txt.process",
            return_value="Document body",
        ),
        patch(
            "aymurai.text.extractors.docx.get_footnotes",
            return_value=["Footnote one", ""],
        ),
    ):
        extractor = DocxExtractor()
        result = extractor.extract(file_path)

    assert "Document body" in result
    assert result.strip().endswith("Footnote one")


def test_docx_extractor_raises_invalid_file(tmp_path: Path) -> None:
    file_path = tmp_path / "broken.docx"
    file_path.write_bytes(b"")

    with patch(
        "aymurai.text.extractors.docx.docx2txt.process",
        side_effect=OSError("boom"),
    ):
        extractor = DocxExtractor()
        with pytest.raises(InvalidFile):
            extractor.extract(file_path)


def test_odt_extractor_prepends_header(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.odt"
    file_path.write_bytes(b"fake odt content")

    with (
        patch(
            "aymurai.text.extractors.odt.odt_to_text",
            return_value="Paragraph one",
        ),
        patch(
            "aymurai.text.extractors.odt.get_header",
            return_value=["Header"],
        ),
    ):
        extractor = OdtExtractor()
        result = extractor.extract(file_path)

    assert result.startswith("Header")
    assert "Paragraph one" in result


def test_odt_extractor_invalid_file(tmp_path: Path) -> None:
    file_path = tmp_path / "broken.odt"
    file_path.write_bytes(b"")

    with patch(
        "aymurai.text.extractors.odt.odt_to_text",
        side_effect=ValueError("bad xml"),
    ):
        extractor = OdtExtractor()
        with pytest.raises(InvalidFile):
            extractor.extract(file_path)


def test_pdf_extractor_delegates(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"fake pdf")

    with patch(
        "aymurai.text.extractors.pdf.pdf_to_text",
        return_value="PDF text",
    ):
        extractor = PdfExtractor()
        result = extractor.extract(file_path)

    assert result == "PDF text"


def test_pdf_extractor_passes_config(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.pdf"
    file_path.write_bytes(b"fake pdf")

    with patch(
        "aymurai.text.extractors.pdf.pdf_to_text",
        return_value="PDF text",
    ) as pdf_to_text:
        extractor = PdfExtractor()
        extractor.extract(
            file_path,
            use_cache=False,
            layout_batch_size=4,
            detection_batch_size=5,
            table_rec_batch_size=6,
            recognition_batch_size=7,
            ocr_error_batch_size=8,
            force_ocr=False,
            strip_existing_ocr=False,
            torch_device="cpu",
            debug=True,
        )

    pdf_to_text.assert_called_once_with(
        file_path,
        layout_batch_size=4,
        detection_batch_size=5,
        table_rec_batch_size=6,
        recognition_batch_size=7,
        ocr_error_batch_size=8,
        force_ocr=False,
        strip_existing_ocr=False,
        torch_device="cpu",
        debug=True,
    )


def test_pdf_extractor_wraps_errors(tmp_path: Path) -> None:
    file_path = tmp_path / "broken.pdf"
    file_path.write_bytes(b"")

    with patch(
        "aymurai.text.extractors.pdf.pdf_to_text",
        side_effect=ValueError("invalid"),
    ):
        extractor = PdfExtractor()
        with pytest.raises(InvalidFile):
            extractor.extract(file_path)


def test_odt_extractor_ignores_extra_kwargs(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.odt"
    file_path.write_bytes(b"fake odt content")

    with (
        patch(
            "aymurai.text.extractors.odt.odt_to_text",
            return_value="Paragraph one",
        ),
        patch(
            "aymurai.text.extractors.odt.get_header",
            return_value=[],
        ),
    ):
        extractor = OdtExtractor()
        result = extractor.extract(file_path, layout_batch_size=4)

    assert "Paragraph one" in result
