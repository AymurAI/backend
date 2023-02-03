from multiprocessing import cpu_count
from typing import Iterable, Optional

import spacy
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
from tqdm.auto import tqdm
import tensorflow_text  # noqa
from more_itertools import chunked

from aymurai.logging import get_logger

logger = get_logger(__name__)

N_JOBS = cpu_count()


class USEMQA:
    """
    Base class for USEM (Universal Sentence Encoder Multilingual QA)
    """

    def __init__(
        self,
        usem_qa_url: str = "https://tfhub.dev/google/universal-sentence-encoder-multilingual-qa/3",
    ):
        self.nlp = spacy.blank("xx")
        self.embed = hub.load(usem_qa_url)

    def normalize_text(self, text: str) -> str:
        tokens = self.nlp(text)
        tokens = (token.text for token in tokens if not token.is_punct)
        text = " ".join(tokens).lower()

        return text

    def encode(
        self,
        text_array: list[str],
        encoder_type: str,
        context_array: Optional[list[str]] = None,
    ) -> np.ndarray:
        input_array = [self.normalize_text(text) for text in text_array]

        if encoder_type == "response_encoder":
            encoder_params = {
                "input": tf.constant(input_array),
                "context": tf.constant(context_array),
            }

        if encoder_type == "question_encoder":
            encoder_params = {
                "input": tf.constant(input_array),
            }

        encoded = self.embed.signatures[encoder_type](**encoder_params)
        encoded = encoded["outputs"]

        return encoded

    def batch_encode(
        self,
        text_array: Iterable[str],
        encoder_type: str,
        batch_size: int = 256,
    ) -> np.ndarray:
        text_chunks = chunked(text_array, batch_size)

        encoded = [
            self.encode(text_chunk, encoder_type)
            for text_chunk in tqdm(
                text_chunks,
                desc="creating USEM vectors...",
                total=len(text_array) // batch_size,
            )
        ]

        encoded = np.vstack(encoded)

        return encoded


class SentenceRetrieval:
    def __init__(
        self,
        categories: list[str],
        response_embeddings_path: str,
    ):
        self.usem = USEMQA()
        self.categories = categories
        self.usem_vectors = self.load_usem_vectors(response_embeddings_path)

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
