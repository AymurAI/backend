"""Sentence encoder implementations and retrieval utilities."""

import numpy as np

from aymurai.models.sentence_encoder.base import BaseSentenceEncoder
from aymurai.models.sentence_encoder.factory import EncoderType, create_encoder


class SentenceRetrieval:
    """Retrieve similar sentences using sentence embeddings."""

    def __init__(
        self,
        categories: list[str],
        response_embeddings_path: str,
        encoder: BaseSentenceEncoder | None = None,
        encoder_type: EncoderType | None = None,
    ):
        """
        Initialize SentenceRetrieval.

        Args:
            categories: List of category labels.
            response_embeddings_path: Path to pre-computed embeddings (.npz file).
            encoder: Pre-configured encoder instance. If None, creates one using factory. Defaults to None.
            encoder_type: Type of encoder to create if encoder is None. When None, reads from
                            SENTENCE_ENCODER_TYPE env var. Defaults to None.
        """
        self.encoder = encoder if encoder is not None else create_encoder(encoder_type)
        self.categories = categories
        self.response_vectors = self._load_response_vectors(response_embeddings_path)

    def _load_response_vectors(self, file_path):
        response_vectors = np.load(file_path)
        return response_vectors

    def retrieve(self, text: str, top_k: int = 10) -> list[str]:
        query_vector = self.encoder.encode(
            [text],
            encoder_type="question_encoder",
        )

        products = np.inner(query_vector, self.response_vectors)[0]
        similar_idx = np.flip(products.argsort())[:top_k]
        similar_sentences = [self.categories[idx] for idx in similar_idx]

        return similar_sentences
