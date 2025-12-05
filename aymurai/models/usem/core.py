"""Sentence encoder implementations and retrieval utilities."""

from typing import TYPE_CHECKING, Optional

import numpy as np

from aymurai.models.usem.base import BaseSentenceEncoder
from aymurai.models.usem.factory import EncoderType, create_encoder

# Type hints only - no runtime import
if TYPE_CHECKING:
    from aymurai.models.usem.tensorflow_encoder import TensorFlowUSEEncoder
    from aymurai.models.usem.sentence_transformers_encoder import (
        DistilUSEEncoder,
        MultilingualMiniLMEncoder,
    )


class SentenceRetrieval:
    """Retrieve similar sentences using sentence embeddings."""

    def __init__(
        self,
        categories: list[str],
        response_embeddings_path: str,
        encoder: Optional[BaseSentenceEncoder] = None,
        encoder_type: Optional[EncoderType] = None,
    ):
        """
        Initialize SentenceRetrieval.

        Args:
            categories: List of category labels.
            response_embeddings_path: Path to pre-computed embeddings (.npy file).
            encoder: Pre-configured encoder instance. If None, creates one using factory.
            encoder_type: Type of encoder to create if encoder is None.
                          If None, reads from SENTENCE_ENCODER_TYPE env var.
        """
        self.encoder = encoder if encoder is not None else create_encoder(encoder_type)
        self.categories = categories
        self.usem_vectors = self.load_usem_vectors(response_embeddings_path)

        # Backwards compatibility alias
        self.usem = self.encoder

    def load_usem_vectors(self, file_path):
        usem_vectors = np.load(file_path)
        return usem_vectors

    def retrieve(self, text: str, top_k: int = 10) -> list[str]:
        query_vector = self.usem.encode(
            [text],
            encoder_type="question_encoder",
        )

        products = np.inner(query_vector, self.usem_vectors)[0]
        similar_idx = np.flip(products.argsort())[:top_k]
        similar_sentences = [self.categories[idx] for idx in similar_idx]

        return similar_sentences
