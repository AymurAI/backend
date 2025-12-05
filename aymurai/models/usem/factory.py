"""
Factory for creating sentence encoder instances based on configuration.
"""

import os
import platform
from enum import Enum
from typing import Optional

from aymurai.logger import get_logger
from aymurai.models.usem.base import BaseSentenceEncoder

logger = get_logger(__name__)


class EncoderType(str, Enum):
    """Available encoder implementations."""

    TENSORFLOW_USE = "tensorflow"
    DISTILUSE = "distiluse"
    MINILM = "minilm"
    AUTO = "auto"


def _is_apple_silicon() -> bool:
    """Check if running on Apple Silicon."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _get_encoder_type_from_env() -> EncoderType:
    """Get encoder type from environment variable."""
    env_value = os.getenv("SENTENCE_ENCODER_TYPE", "auto").lower()
    try:
        return EncoderType(env_value)
    except ValueError:
        logger.warning(
            f"Invalid SENTENCE_ENCODER_TYPE '{env_value}', falling back to 'auto'"
        )
        return EncoderType.AUTO


def create_encoder(
    encoder_type: Optional[EncoderType] = None,
    device: Optional[str] = None,
) -> BaseSentenceEncoder:
    """
    Factory function to create the appropriate sentence encoder.

    Args:
        encoder_type: Type of encoder to create. If None, reads from
                      SENTENCE_ENCODER_TYPE env var (defaults to 'auto').
        device: Device for sentence-transformers models (ignored for TensorFlow).

    Returns:
        An instance of BaseSentenceEncoder.

    Environment Variables:
        SENTENCE_ENCODER_TYPE: One of 'tensorflow', 'distiluse', 'minilm', 'auto'.
            - 'tensorflow': Use TensorFlow Hub USE-QA (not compatible with Apple Silicon)
            - 'distiluse': Use distiluse-base-multilingual-cased-v2
            - 'minilm': Use paraphrase-multilingual-MiniLM-L12-v2
            - 'auto': Auto-detect based on platform (Apple Silicon -> distiluse, else tensorflow)

    Raises:
        ImportError: If required dependencies are not available.
        ValueError: If an invalid encoder type is specified.
    """
    if encoder_type is None:
        encoder_type = _get_encoder_type_from_env()

    # Auto-detect based on platform
    if encoder_type == EncoderType.AUTO:
        if _is_apple_silicon():
            logger.info(
                "Apple Silicon detected, using DistilUSE encoder for compatibility"
            )
            encoder_type = EncoderType.DISTILUSE
        else:
            logger.info("Using TensorFlow USE encoder")
            encoder_type = EncoderType.TENSORFLOW_USE

    # Create the appropriate encoder
    if encoder_type == EncoderType.TENSORFLOW_USE:
        from aymurai.models.usem.tensorflow_encoder import TensorFlowUSEEncoder

        return TensorFlowUSEEncoder()

    elif encoder_type == EncoderType.DISTILUSE:
        from aymurai.models.usem.sentence_transformers_encoder import DistilUSEEncoder

        return DistilUSEEncoder(device=device)

    elif encoder_type == EncoderType.MINILM:
        from aymurai.models.usem.sentence_transformers_encoder import (
            MultilingualMiniLMEncoder,
        )

        return MultilingualMiniLMEncoder(device=device)

    else:
        raise ValueError(f"Unknown encoder type: {encoder_type}")


# Backwards compatibility alias
def get_encoder(**kwargs) -> BaseSentenceEncoder:
    """Alias for create_encoder for backwards compatibility."""
    return create_encoder(**kwargs)
