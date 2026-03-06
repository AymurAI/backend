from pathlib import Path
from unittest.mock import patch

import pytest

from aymurai.text.extraction import ERRORS, InvalidFile, extract_document, get_extension


class DummyExtractor:
    def __init__(self) -> None:
        self.called = False
        self.called_path: Path | None = None

    def extract(self, path: Path, **_: object) -> str:
        self.called = True
        self.called_path = path
        return "ok"


class BoomInvalidExtractor:
    def extract(self, _path: Path, **_: object) -> str:
        raise InvalidFile("boom")


class BoomRuntimeExtractor:
    def extract(self, _path: Path, **_: object) -> str:
        raise RuntimeError("boom")


def test_extract_document_dispatches(tmp_path: Path) -> None:
    source = tmp_path / "document.docx"
    source.write_text("dummy")
    dummy = DummyExtractor()

    with patch(
        "aymurai.text.extraction.get_extractor",
        return_value=dummy,
    ):
        result = extract_document(source)

    assert result == "ok"
    assert dummy.called is True
    assert dummy.called_path == source


def test_extract_document_missing_file_raises() -> None:
    missing = Path("/no/such/file.pdf")
    with pytest.raises(InvalidFile):
        extract_document(missing, errors="raise")


def test_extract_document_handles_invalid_file(tmp_path: Path) -> None:
    source = tmp_path / "document.pdf"
    source.write_text("dummy")

    with patch(
        "aymurai.text.extraction.get_extractor",
        return_value=BoomInvalidExtractor(),
    ):
        result = extract_document(source, errors="ignore")

    assert result is None


def test_extract_document_raises_unexpected(tmp_path: Path) -> None:
    source = tmp_path / "document.odt"
    source.write_text("dummy")

    with patch(
        "aymurai.text.extraction.get_extractor",
        return_value=BoomRuntimeExtractor(),
    ):
        with pytest.raises(RuntimeError):
            extract_document(source, errors="raise")


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("file.pdf", "pdf"),
        ("file.docx", "docx"),
        ("file.odt", "odt"),
        ("file.unknown", "unknown"),
    ],
)
def test_get_extension_basic(filename: str, expected: str) -> None:
    assert get_extension(filename) == expected


def test_errors_configured() -> None:
    assert set(ERRORS) == {"ignore", "coerce", "raise"}
