from hashlib import blake2b
from pathlib import Path

from aymurai.logger import get_logger
from aymurai.text.extractors.base import BaseExtractor, InvalidFile, register_extractor
from aymurai.text.extractors.utils import pdf_to_text
from aymurai.utils.cache import cache_load, cache_save, get_cache_key

logger = get_logger(__file__)


@register_extractor
class PdfExtractor(BaseExtractor):
    extension = "pdf"

    def extract(
        self,
        path: Path,
        y_tolerance: float | None = None,
        *,
        use_cache: bool = True,
        debug: bool | None = None,
    ) -> str:
        """
        Extract normalized text from a PDF document.

        Args:
            path (Path): Input document path.
            use_cache (bool): Toggle extractor-level caching. Defaults to True.
            debug (bool | None): Optional override for marker debug mode. Defaults to None.

        Returns:
            str: Cleaned textual content.
        """
        file_path = self.ensure_file(path)

        # Check cache first when enabled
        cache_key = self._cache_key(file_path) if use_cache else None
        if use_cache and cache_key:
            cached_text = cache_load(cache_key)
            if cached_text is not None:
                logger.debug("PDF cache hit for %s", file_path)
                return cached_text

        try:
            text = pdf_to_text(
                file_path,
                y_tolerance=y_tolerance,
                debug=debug,
            )
        except (OSError, ValueError) as exc:
            raise InvalidFile(str(exc)) from exc
        except Exception as exc:
            raise InvalidFile(str(exc)) from exc
        if use_cache and cache_key:
            cache_save(text, key=cache_key)
            logger.debug("PDF cache stored for %s", file_path)

        return text

    @staticmethod
    def _cache_key(file_path: Path) -> str | None:
        """
        Compute a stable cache key for the PDF payload.

        Args:
            file_path (Path): Location of the PDF file to fingerprint.

        Returns:
            str | None: Deterministic cache key, or ``None`` when the file is unreadable.
        """
        try:
            stat = file_path.stat()
        except OSError as exc:
            logger.warning("Unable to stat PDF %s for caching: %s", file_path, exc)
            return None

        try:
            hasher = blake2b(digest_size=32)
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    hasher.update(chunk)
            fingerprint = hasher.hexdigest()
        except OSError as exc:
            logger.warning("Unable to hash PDF %s for caching: %s", file_path, exc)
            fingerprint = None

        item = fingerprint or file_path.resolve().as_posix()
        context = {
            "component": "pdf-extractor",
            "size": stat.st_size,
        }
        if fingerprint is None:
            context["mtime_ns"] = stat.st_mtime_ns

        return get_cache_key(item, context=context)
