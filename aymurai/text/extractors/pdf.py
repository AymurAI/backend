from pathlib import Path

from aymurai.logger import get_logger
from aymurai.text.extractors.base import BaseExtractor, InvalidFile, register_extractor
from aymurai.text.extractors.utils import pdf_to_text
from aymurai.utils.cache import cache_load, cache_save, get_cache_key

logger = get_logger(__file__)


@register_extractor
class PdfExtractor(BaseExtractor):
    extension = "pdf"

    def extract(self, path: Path) -> str:
        file_path = self.ensure_file(path)

        # Check cache first
        cache_key = self._cache_key(file_path)
        if cache_key:
            cached_text = cache_load(cache_key)
            if cached_text is not None:
                logger.debug("PDF cache hit for %s", file_path)
                return cached_text

        try:
            text = pdf_to_text(file_path)
        except (OSError, ValueError) as exc:
            raise InvalidFile(str(exc)) from exc
        except Exception as exc:
            raise InvalidFile(str(exc)) from exc
        if cache_key:
            cache_save(text, key=cache_key)
            logger.debug("PDF cache stored for %s", file_path)

        return text

    @staticmethod
    def _cache_key(file_path: Path) -> str | None:
        """
        Generate a cache key based on the file path and its metadata.

        Args:
            file_path (Path): Path to the PDF file.

        Returns:
            str | None: Cache key string or None if stat fails.
        """
        try:
            stat = file_path.stat()
        except OSError as exc:
            logger.warning("Unable to stat PDF %s for caching: %s", file_path, exc)
            return None

        return get_cache_key(
            file_path.resolve().as_posix(),
            context={
                "component": "pdf-extractor",
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
            },
        )
