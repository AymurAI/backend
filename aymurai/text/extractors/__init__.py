# Import concrete extractors so they self-register.
from aymurai.text.extractors import docx, odt, pdf  # noqa: F401
from aymurai.text.extractors.base import (
    BaseExtractor,
    InvalidFile,
    get_extractor,
    register_extractor,
    supported_extensions,
)

SUPPORTED_EXTENSIONS = supported_extensions()

__all__ = [
    "BaseExtractor",
    "InvalidFile",
    "SUPPORTED_EXTENSIONS",
    "get_extractor",
    "register_extractor",
]
