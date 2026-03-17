from pathlib import Path
from typing import Any

from aymurai.text.extractors.base import BaseExtractor, InvalidFile, register_extractor
from aymurai.text.extractors.utils import pdf_to_text


@register_extractor
class PdfExtractor(BaseExtractor):
    extension = "pdf"

    def extract(self, path: Path, **_: Any) -> str:
        file_path = self.ensure_file(path)

        try:
            return pdf_to_text(file_path)
        except (OSError, ValueError) as exc:
            raise InvalidFile(str(exc)) from exc
        except Exception as exc:
            raise InvalidFile(str(exc)) from exc
