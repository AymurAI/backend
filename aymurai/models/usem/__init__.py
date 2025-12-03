"""Sentence encoder module with multiple backend implementations.

Implementations are lazily loaded to avoid importing unavailable dependencies.
Use the factory function `create_encoder()` for automatic backend selection,
or import specific implementations directly from their modules:

    from aymurai.models.usem.tensorflow_encoder import TensorFlowUSEEncoder
    from aymurai.models.usem.sentence_transformers_encoder import DistilUSEEncoder
"""

from aymurai.models.usem.base import BaseSentenceEncoder
from aymurai.models.usem.factory import EncoderType, create_encoder, get_encoder
from aymurai.models.usem.core import SentenceRetrieval


def __getattr__(name: str):
    """Lazy loading of encoder implementations."""
    if name == "TensorFlowUSEEncoder" or name == "USEMQA":
        from aymurai.models.usem.tensorflow_encoder import TensorFlowUSEEncoder
        return TensorFlowUSEEncoder
    
    if name == "DistilUSEEncoder":
        from aymurai.models.usem.sentence_transformers_encoder import DistilUSEEncoder
        return DistilUSEEncoder
    
    if name == "MultilingualMiniLMEncoder":
        from aymurai.models.usem.sentence_transformers_encoder import MultilingualMiniLMEncoder
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
    "TensorFlowUSEEncoder",
    "DistilUSEEncoder",
    "MultilingualMiniLMEncoder",
    # Backwards compatibility (lazy loaded)
    "USEMQA",
    # Retrieval
    "SentenceRetrieval",
]
