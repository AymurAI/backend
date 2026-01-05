import re
from typing import Callable

import numpy as np


class BM25Scorer:
    """Lightweight BM25 scorer over subcategory strings."""

    def __init__(self, subcategories: list[str], normalize_fn: Callable[[str], str]):
        """
        Initialize the BM25Scorer with subcategories and a normalization function.

        Args:
            subcategories (list[str]): List of subcategory strings to be scored.
            normalize_fn (Callable[[str], str]): Function to normalize text before tokenization.
        """
        self.subcategories = subcategories
        self.token_pattern = re.compile(r"\w+", re.UNICODE)
        self.normalize_fn = normalize_fn

        tokenized = [self._tokenize(sub) for sub in subcategories]
        self.doc_len = [len(toks) for toks in tokenized]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0.0
        self.N = len(tokenized)
        self.doc_freqs = [self._to_counter(toks) for toks in tokenized]
        corpus_tokens = set().union(*self.doc_freqs) if self.doc_freqs else set()
        self.df = {
            token: sum(1 for doc in self.doc_freqs if token in doc)
            for token in corpus_tokens
        }
        # Using BM25+ style IDF smoothing
        self.idf = {
            token: np.log(1 + (self.N - freq + 0.5) / (freq + 0.5))
            for token, freq in self.df.items()
        }

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize the input text after normalization.

        Args:
            text (str): Input text to tokenize.

        Returns:
            list[str]: List of tokens.
        """
        normalized = self.normalize_fn(text)
        return self.token_pattern.findall(normalized)

    def _to_counter(self, tokens: list[str]) -> dict[str, int]:
        """
        Convert a list of tokens into a frequency counter.

        Args:
            tokens (list[str]): List of tokens.

        Returns:
            dict[str, int]: Frequency counter of tokens.
        """
        counts = {}

        for t in tokens:
            counts[t] = counts.get(t, 0) + 1

        return counts

    def score_vector(self, text: str, k1: float = 1.2, b: float = 0.75) -> np.ndarray:
        """
        Compute BM25 scores for the input text against all subcategories.

        Args:
            text (str): Input text to score.
            k1 (float, optional): BM25 k1 parameter. Defaults to 1.2.
            b (float, optional): BM25 b parameter. Defaults to 0.75.

        Returns:
            np.ndarray:
        """
        scores = np.zeros(self.N, dtype=np.float64)
        tokens = self._tokenize(text)

        for token in tokens:
            idf = self.idf.get(token)
            if idf is None:
                continue

            for idx, freq_map in enumerate(self.doc_freqs):
                freq = freq_map.get(token, 0)
                if freq == 0:
                    continue

                # BM25 scoring formula
                denom = freq + k1 * (
                    1 - b + b * self.doc_len[idx] / (self.avgdl + 1e-9)
                )

                # Update score
                scores[idx] += idf * freq * (k1 + 1) / denom

        return scores
