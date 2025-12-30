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


def _coerce_encoder_type(value: EncoderType | str | None) -> EncoderType:
    """
    Normalize encoder type values into EncoderType.

    Args:
        value: Encoder type as EncoderType, string, or None. If None, reads from env var.

    Returns:
        EncoderType: Normalized encoder type.
    """
    if value is None:
        return _get_encoder_type_from_env()

    if isinstance(value, EncoderType):
        return value

    if isinstance(value, str):
        try:
            return EncoderType(value.lower())
        except ValueError as exc:
            raise ValueError(f"Unknown encoder type: {value}") from exc

    raise TypeError(f"Unsupported encoder type value: {type(value)!r}")


def create_encoder(
    encoder_type: EncoderType | str | None = None,
    device: Optional[str] = None,
) -> BaseSentenceEncoder:
    """
    Factory function to create the appropriate sentence encoder.

    Args:
        encoder_type: Type of encoder to create. Accepts EncoderType or string.
                      If None, reads from SENTENCE_ENCODER_TYPE env var
                      (defaults to 'distiluse').
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
    encoder_type = _coerce_encoder_type(encoder_type)

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
