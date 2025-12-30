"""Sentence encoder module with sentence-transformers backends.

Implementations are lazily loaded to avoid importing unavailable dependencies.
Use the factory function `create_encoder()` for automatic backend selection,
or import specific implementations directly from their modules:

    from aymurai.models.sentence_encoder.sentence_transformers_encoder import DistilUSEEncoder
"""

from aymurai.models.sentence_encoder.base import BaseSentenceEncoder
from aymurai.models.sentence_encoder.factory import (
    EncoderType,
    create_encoder,
    get_encoder,
)
from aymurai.models.sentence_encoder.core import SentenceRetrieval


def __getattr__(name: str):
    """Lazy loading of encoder implementations."""
    if name == "DistilUSEEncoder":
        from aymurai.models.sentence_encoder.sentence_transformers_encoder import (
            DistilUSEEncoder,
        )

        return DistilUSEEncoder

    if name == "MultilingualMiniLMEncoder":
        from aymurai.models.sentence_encoder.sentence_transformers_encoder import (
            MultilingualMiniLMEncoder,
        )

        return MultilingualMiniLMEncoder

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base interface
    "BaseSentenceEncoder",
    # Factory
    "EncoderType",
    "create_encoder",
    "get_encoder",
    # Implementations (lazy loaded)
    "DistilUSEEncoder",
    "MultilingualMiniLMEncoder",
    # Retrieval
    "SentenceRetrieval",
]
