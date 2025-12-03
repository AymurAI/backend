"""
TensorFlow Hub Universal Sentence Encoder implementation.
"""

from multiprocessing import cpu_count
from typing import Iterable, Optional

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
import tensorflow_text  # noqa
from more_itertools import chunked
from tqdm.auto import tqdm

from aymurai.logger import get_logger
from aymurai.models.usem.base import BaseSentenceEncoder

logger = get_logger(__name__)

N_JOBS = cpu_count()


class TensorFlowUSEEncoder(BaseSentenceEncoder):
    """
    TensorFlow Hub Universal Sentence Encoder Multilingual QA implementation.

    This implementation requires tensorflow-text which is not available on Apple Silicon.
    Use SentenceTransformersEncoder for macOS ARM64 compatibility.
    """

    def __init__(
        self,
        usem_qa_url: str = "https://tfhub.dev/google/universal-sentence-encoder-multilingual-qa/3",
    ):
        self.embed = hub.load(usem_qa_url)

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
        text_list = list(text_array)
        text_chunks = chunked(text_list, batch_size)

        encoded = [
            self.encode(list(text_chunk), encoder_type)
            for text_chunk in tqdm(
                text_chunks,
                desc="creating USEM vectors...",
                total=len(text_list) // batch_size,
            )
        ]

        encoded = np.vstack(encoded)

        return encoded
