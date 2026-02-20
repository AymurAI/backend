from pathlib import Path

from aymurai.text.extractors.base import BaseExtractor, InvalidFile, register_extractor
from aymurai.text.extractors.utils import pdf_to_text


@register_extractor
class PdfExtractor(BaseExtractor):
    extension = "pdf"

    def extract(
        self,
        path: Path,
        y_tolerance: float | None = None,
    ) -> str:
        """
        Extract normalized text from a PDF document.

        Args:
            path (Path): Input document path.
            y_tolerance (float | None, optional): Maximum vertical gap used to
                merge nearby text blocks. If None, it is estimated from the
                document. Defaults to None.

        Returns:
            str: Cleaned textual content.

        Raises:
            InvalidFile: If the file is unreadable or extraction fails.
        """
        file_path = self.ensure_file(path)

        try:
            return pdf_to_text(file_path, y_tolerance=y_tolerance)
        except (OSError, ValueError) as exc:
            raise InvalidFile(str(exc)) from exc
        except Exception as exc:
            raise InvalidFile(str(exc)) from exc
