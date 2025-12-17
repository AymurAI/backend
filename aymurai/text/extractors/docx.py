from pathlib import Path
from zipfile import BadZipFile

import docx2txt

from aymurai.text.extractors.base import BaseExtractor, InvalidFile, register_extractor
from aymurai.text.extractors.utils import get_footnotes, normalize_text


@register_extractor
class DocxExtractor(BaseExtractor):
    extension = "docx"

    def extract(self, path: Path) -> str:
        file_path = self.ensure_file(path)

        try:
            document_text = docx2txt.process(str(file_path)) or ""
        except (OSError, BadZipFile, KeyError) as exc:
            raise InvalidFile(str(exc)) from exc
        except Exception as exc:
            raise InvalidFile(str(exc)) from exc

        footnotes = get_footnotes(file_path) or []
        footnotes_text = "\n".join(note for note in footnotes if note.strip())

        if footnotes_text:
            document_text = f"{document_text}\n\n{footnotes_text}"

        return normalize_text(document_text)
