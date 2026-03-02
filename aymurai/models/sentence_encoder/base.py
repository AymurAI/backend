"""
Abstract base class for sentence encoders.
"""

import unicodedata
from abc import ABC, abstractmethod
from typing import Iterable, Optional

import numpy as np


class BaseSentenceEncoder(ABC):
    """
    Abstract base class defining the interface for sentence encoders.
    All encoder implementations must inherit from this class.
    """

    def normalize_text(self, text: str) -> str:
        """Normalize text by lowercasing and removing non-alphanumeric characters."""
        text = text.lower()
        text = "".join(
            char
            for char in unicodedata.normalize("NFKD", text)
            if char.isalnum() or char.isspace()
        )
        return text

    @abstractmethod
    def encode(
        self,
        text_array: list[str],
        encoder_type: str,
        context_array: Optional[list[str]] = None,
    ) -> np.ndarray:
        """
        Encode a list of texts into embeddings.

        Args:
            text_array: List of texts to encode.
            encoder_type: Type of encoder to use ('question_encoder' or 'response_encoder').
            context_array: Optional context for response encoding.

        Returns:
            numpy array of embeddings.
        """
        pass

    @abstractmethod
    def batch_encode(
        self,
        text_array: Iterable[str],
        encoder_type: str,
        batch_size: int = 256,
    ) -> np.ndarray:
        """
        Encode texts in batches.

        Args:
            text_array: Iterable of texts to encode.
            encoder_type: Type of encoder to use.
            batch_size: Number of texts per batch.

        Returns:
            numpy array of embeddings.
        """
        pass
