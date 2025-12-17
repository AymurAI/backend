import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aymurai.text.extraction import ERRORS, InvalidFile, extract_document, get_extension


class ExtractionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.tmp_path = Path(self.tempdir.name)

    def test_extract_document_dispatches(self):
        source = self.tmp_path / "document.docx"
        source.write_text("dummy")

        class DummyExtractor:
            def __init__(self) -> None:
                self.called = False
                self.called_path: Path | None = None

            def extract(self, path: Path) -> str:
                self.called = True
                self.called_path = path
                return "ok"

        dummy = DummyExtractor()

        with patch(
            "aymurai.text.extraction.get_extractor",
            return_value=dummy,
        ):
            result = extract_document(source)

        self.assertEqual(result, "ok")
        self.assertTrue(dummy.called)
        self.assertEqual(dummy.called_path, source)

    def test_extract_document_missing_file_raises(self):
        missing = Path("/no/such/file.pdf")
        with self.assertRaises(InvalidFile):
            extract_document(missing, errors="raise")

    def test_extract_document_handles_invalid_file(self):
        source = self.tmp_path / "document.pdf"
        source.write_text("dummy")

        class BoomExtractor:
            def extract(self, _path: Path) -> str:
                raise InvalidFile("boom")

        with patch(
            "aymurai.text.extraction.get_extractor",
            return_value=BoomExtractor(),
        ):
            result = extract_document(source, errors="ignore")

        self.assertIsNone(result)

    def test_extract_document_raises_unexpected(self):
        source = self.tmp_path / "document.odt"
        source.write_text("dummy")

        class BoomExtractor:
            def extract(self, _path: Path) -> str:
                raise RuntimeError("boom")

        with patch(
            "aymurai.text.extraction.get_extractor",
            return_value=BoomExtractor(),
        ):
            with self.assertRaises(RuntimeError):
                extract_document(source, errors="raise")

    def test_get_extension_basic(self):
        cases = [
            ("file.pdf", "pdf"),
            ("file.docx", "docx"),
            ("file.odt", "odt"),
            ("file.unknown", "unknown"),
        ]

        for filename, expected in cases:
            with self.subTest(filename=filename):
                self.assertEqual(get_extension(filename), expected)

    def test_errors_configured(self):
        self.assertEqual(set(ERRORS), {"ignore", "coerce", "raise"})


if __name__ == "__main__":
    unittest.main()
