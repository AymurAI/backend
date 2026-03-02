from pathlib import Path
from typing import Any
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from aymurai.text.extractors.base import BaseExtractor, InvalidFile, register_extractor
from aymurai.text.extractors.utils import get_header, normalize_text, odt_to_text


@register_extractor
class OdtExtractor(BaseExtractor):
    extension = "odt"

    def extract(self, path: Path, **_: Any) -> str:
        file_path = self.ensure_file(path)

        try:
            document_text = odt_to_text(file_path)
        except (OSError, ValueError, BadZipFile, KeyError, ParseError) as exc:
            raise InvalidFile(str(exc)) from exc

        header = "\n".join(get_header(file_path)).strip()
        if header:
            document_text = f"{header}\n\n{document_text}"

        return normalize_text(document_text)
