"""
Factory for creating sentence encoder instances based on configuration.
"""

import os
from enum import Enum
from typing import Optional

from aymurai.logger import get_logger
from aymurai.models.sentence_encoder.base import BaseSentenceEncoder

logger = get_logger(__name__)


class EncoderType(str, Enum):
    """Available encoder implementations."""

    DISTILUSE = "distiluse"
    MINILM = "minilm"


def _get_encoder_type_from_env() -> EncoderType:
    """Get encoder type from environment variable."""
    env_value = os.getenv("SENTENCE_ENCODER_TYPE", "distiluse").lower()
    try:
        return EncoderType(env_value)
    except ValueError:
        logger.warning(
            f"Invalid SENTENCE_ENCODER_TYPE '{env_value}', falling back to 'distiluse'"
        )
        return EncoderType.DISTILUSE


def create_encoder(
    encoder_type: Optional[EncoderType] = None,
    device: Optional[str] = None,
) -> BaseSentenceEncoder:
    """
    Factory function to create the appropriate sentence encoder.

    Args:
        encoder_type: Type of encoder to create. If None, reads from
                      SENTENCE_ENCODER_TYPE env var (defaults to 'distiluse').
        device: Device for sentence-transformers models.

    Returns:
        An instance of BaseSentenceEncoder.

    Environment Variables:
        SENTENCE_ENCODER_TYPE: One of 'distiluse', 'minilm'.
            - 'distiluse': Use distiluse-base-multilingual-cased-v2
            - 'minilm': Use paraphrase-multilingual-MiniLM-L12-v2

    Raises:
        ImportError: If required dependencies are not available.
        ValueError: If an invalid encoder type is specified.
    """
    if encoder_type is None:
        encoder_type = _get_encoder_type_from_env()

    # Create the appropriate encoder
    if encoder_type == EncoderType.DISTILUSE:
        from aymurai.models.sentence_encoder.sentence_transformers_encoder import (
            DistilUSEEncoder,
        )

        return DistilUSEEncoder(device=device)

    elif encoder_type == EncoderType.MINILM:
        from aymurai.models.sentence_encoder.sentence_transformers_encoder import (
            MultilingualMiniLMEncoder,
        )

        return MultilingualMiniLMEncoder(device=device)

    else:
        raise ValueError(f"Unknown encoder type: {encoder_type}")


# Backwards compatibility alias
def get_encoder(**kwargs) -> BaseSentenceEncoder:
    """Alias for create_encoder for backwards compatibility."""
    return create_encoder(**kwargs)
