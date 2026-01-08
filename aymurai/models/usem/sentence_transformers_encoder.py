"""
Sentence Transformers encoder implementations.
Compatible with Apple Silicon (M1/M2/M3) via PyTorch MPS backend.
"""

from typing import Iterable, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from aymurai.logger import get_logger
from aymurai.models.usem.base import BaseSentenceEncoder

logger = get_logger(__name__)


class DistilUSEEncoder(BaseSentenceEncoder):
    """
    Knowledge-distilled Universal Sentence Encoder using sentence-transformers.

    This is a PyTorch-based distillation of the original USE multilingual model.
    Supports 50+ languages and produces 512-dimensional embeddings.

    Compatible with Apple Silicon via MPS backend.
    """

    MODEL_NAME = "sentence-transformers/distiluse-base-multilingual-cased-v2"

    def __init__(self, device: Optional[str] = None):
        """
        Initialize the DistilUSE encoder.

        Args:
            device: Device to run the model on. If None, auto-detects
                    (will use 'mps' on Apple Silicon, 'cuda' if available, else 'cpu').
        """
        self.model = SentenceTransformer(self.MODEL_NAME, device=device)
        logger.info(f"Loaded {self.MODEL_NAME} on device: {self.model.device}")

    def encode(
        self,
        text_array: list[str],
        encoder_type: str,
        context_array: Optional[list[str]] = None,
    ) -> np.ndarray:
        """
        Encode texts into embeddings.

        Note: encoder_type and context_array are kept for API compatibility
        but are not used since sentence-transformers uses a single encoder.
        """
        input_array = [self.normalize_text(text) for text in text_array]
        return self.model.encode(input_array, convert_to_numpy=True)

    def batch_encode(
        self,
        text_array: Iterable[str],
        encoder_type: str,
        batch_size: int = 256,
    ) -> np.ndarray:
        """Encode texts in batches with progress bar."""
        text_list = list(text_array)
        input_array = [self.normalize_text(text) for text in text_list]
        return self.model.encode(
            input_array,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
        )


class MultilingualMiniLMEncoder(BaseSentenceEncoder):
    """
    Multilingual MiniLM encoder using sentence-transformers.

    Higher quality embeddings than DistilUSE with faster inference.
    Supports 50+ languages and produces 384-dimensional embeddings.

    Compatible with Apple Silicon via MPS backend.
    """

    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, device: Optional[str] = None):
        """
        Initialize the Multilingual MiniLM encoder.

        Args:
            device: Device to run the model on. If None, auto-detects
                    (will use 'mps' on Apple Silicon, 'cuda' if available, else 'cpu').
        """
        self.model = SentenceTransformer(self.MODEL_NAME, device=device)
        logger.info(f"Loaded {self.MODEL_NAME} on device: {self.model.device}")

    def encode(
        self,
        text_array: list[str],
        encoder_type: str,
        context_array: Optional[list[str]] = None,
    ) -> np.ndarray:
        """
        Encode texts into embeddings.

        Note: encoder_type and context_array are kept for API compatibility
        but are not used since sentence-transformers uses a single encoder.
        """
        input_array = [self.normalize_text(text) for text in text_array]
        return self.model.encode(input_array, convert_to_numpy=True)

    def batch_encode(
        self,
        text_array: Iterable[str],
        encoder_type: str,
        batch_size: int = 256,
    ) -> np.ndarray:
        """Encode texts in batches with progress bar."""
        text_list = list(text_array)
        input_array = [self.normalize_text(text) for text in text_list]
        return self.model.encode(
            input_array,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
