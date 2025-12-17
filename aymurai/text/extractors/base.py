from abc import ABC, abstractmethod
from pathlib import Path

from aymurai.logger import get_logger

logger = get_logger(__file__)


class InvalidFile(Exception):
    """Raised when an extractor receives an invalid or missing file."""


class BaseExtractor(ABC):
    """Common interface shared by all document extractors."""

    # Lowercase file extension handled by the extractor, without dot.
    extension: str

    def ensure_file(self, path: Path) -> Path:
        """
        Ensure the input file exists before extraction.

        Args:
            path (Path): Candidate file path.

        Raises:
            InvalidFile: If the file does not exist.

        Returns:
            Path: Validated path ready for extraction.
        """
        if not path.exists():
            raise InvalidFile(f"Invalid path: {path}")
        return path

    @abstractmethod
    def extract(self, path: Path) -> str:
        """
        Extract normalized text from the source document.

        Args:
            path (Path): Input document path.

        Returns:
            str: Cleaned textual content.
        """


_REGISTRY: dict[str, type[BaseExtractor]] = {}


def register_extractor(cls: type[BaseExtractor]) -> type[BaseExtractor]:
    """
    Register an extractor class for a specific extension.

    Args:
        cls (type[BaseExtractor]): Extractor class to register.

    Returns:
        type[BaseExtractor]: Registered class for fluent decorator usage.
    """
    extension = getattr(cls, "extension", None)
    if not extension:
        raise ValueError(
            f"Extractor {cls.__name__} must define an 'extension' attribute"
        )

    normalized = extension.lower()
    if normalized in _REGISTRY:
        logger.warning(
            "Overriding extractor for extension '%s' with %s", normalized, cls.__name__
        )

    _REGISTRY[normalized] = cls
    return cls


def get_extractor(extension: str) -> BaseExtractor:
    """
    Retrieve an extractor instance for the desired extension.

    Args:
        extension (str): File extension to resolve.

    Returns:
        BaseExtractor: Ready-to-use extractor instance.
    """
    normalized = extension.lower()
    try:
        extractor_cls = _REGISTRY[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported extension: {extension}") from exc
    return extractor_cls()


def supported_extensions() -> set[str]:
    """
    List the registered document extensions.

    Returns:
        set[str]: Known extensions handled by the registry.
    """
    return set(_REGISTRY.keys())


__all__ = [
    "BaseExtractor",
    "InvalidFile",
    "get_extractor",
    "register_extractor",
    "supported_extensions",
]
