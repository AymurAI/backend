from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class InvalidDocumentAnonymizer(Exception):
    """Raised when an anonymizer receives an invalid or unsupported document."""


class BaseAnonymizer(ABC):
    """Common interface shared by all document anonymizers."""

    extension: str

    @property
    def __name__(self) -> str:
        return self.__class__.__name__

    def ensure_file(self, path: Path) -> Path:
        if not path.exists():
            raise InvalidDocumentAnonymizer(f"Invalid path: {path}")
        return path

    def __call__(
        self,
        item: dict,
        preds: list[dict],
        output_dir: str = ".",
        render_context: dict[str, Any] | None = None,
    ) -> str:
        return self.anonymize(item, preds, output_dir, render_context=render_context)

    @abstractmethod
    def anonymize(
        self,
        item: dict,
        preds: list[dict],
        output_dir: str = ".",
        render_context: dict[str, Any] | None = None,
    ) -> str:
        """Anonymize a document and return the output path."""


_REGISTRY: dict[str, type[BaseAnonymizer]] = {}


def register_anonymizer(cls: type[BaseAnonymizer]) -> type[BaseAnonymizer]:
    extension = getattr(cls, "extension", None)
    if not extension:
        raise ValueError(
            f"Anonymizer {cls.__name__} must define an 'extension' attribute"
        )

    _REGISTRY[extension.lower()] = cls
    return cls


def get_anonymizer(extension: str) -> BaseAnonymizer:
    normalized = extension.lower()
    try:
        anonymizer_cls = _REGISTRY[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported extension: {extension}") from exc
    return anonymizer_cls()


def supported_extensions() -> set[str]:
    return set(_REGISTRY.keys())


__all__ = [
    "BaseAnonymizer",
    "InvalidDocumentAnonymizer",
    "get_anonymizer",
    "register_anonymizer",
    "supported_extensions",
]
