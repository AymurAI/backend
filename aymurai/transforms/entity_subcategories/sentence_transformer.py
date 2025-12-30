import os
from copy import deepcopy
from pathlib import Path
from typing import Iterable

import numpy as np

from aymurai.logger import get_logger
from aymurai.meta.pipeline_interfaces import Transform
from aymurai.meta.types import DataItem
from aymurai.models.sentence_encoder.base import BaseSentenceEncoder
from aymurai.models.sentence_encoder.factory import create_encoder
from aymurai.transforms.entity_subcategories.bm25 import BM25Scorer
from aymurai.transforms.entity_subcategories.subcategories import SUBCATEGORIES
from aymurai.transforms.entity_subcategories.utils import filter_by_category
from aymurai.utils.misc import get_element

logger = get_logger(__name__)


class SentenceTransformerSubcategorizer(Transform):
    """
    Hybrid sentence-transformer + optional BM25 subcategorizer.

    - When ``bm25_weight > 0`` mixes BM25 and encoder cosine scores.
    - When ``bm25_weight <= 0`` it falls back to encoder-only retrieval.
    - Subcategories are normalized (underscore -> space, then encoder.normalize_text) before encoding.
    """

    def __init__(
        self,
        category: str,
        embeddings_path: str,
        encoder_name: str = "distiluse",
        bm25_weight: float = 0.5,
        device: str | None = None,
        batch_size: int = 256,
        rebuild_embeddings: bool = False,
        encoder: BaseSentenceEncoder | None = None,
    ):
        """
        SentenceTransformerSubcategorizer constructor.

        Args:
            category (str): Category to subcategorize.
            embeddings_path (str): Path to store/load subcategory embeddings.
            encoder_name (str, optional): Name of the encoder to use. Defaults to "distiluse".
            bm25_weight (float, optional): Weight for BM25 scoring. Defaults to 0.5.
            device (str | None, optional): Device to run the encoder on. Defaults to None.
            batch_size (int, optional): Batch size for encoding. Defaults to 256.
            rebuild_embeddings (bool, optional): Whether to rebuild embeddings even if cached ones exist. Defaults to False.
            encoder (BaseSentenceEncoder | None, optional): Encoder instance to use. Defaults to None.
        """
        self.category = category
        self.bm25_weight = float(bm25_weight)
        self.batch_size = batch_size

        cache_root = Path(
            os.getenv("AYMURAI_CACHE_BASEPATH", "/resources/cache/aymurai")
        )
        self.cache_path = cache_root / self.__class__.__name__
        self.cache_path.mkdir(parents=True, exist_ok=True)

        self.subcategories = self._load_subcategories(category)

        self.encoder_name = encoder_name
        self.encoder = encoder or create_encoder(
            encoder_type=encoder_name, device=device
        )

        embeddings_path = Path(embeddings_path)
        if not embeddings_path.is_absolute():
            embeddings_path = self.cache_path / embeddings_path
        embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        self.embeddings_path = embeddings_path

        self.response_vectors = self._load_or_build_embeddings(rebuild_embeddings)
        self.bm25 = (
            BM25Scorer(self.subcategories, normalize_fn=self._normalize_subcategory)
            if self.bm25_weight > 0
            else None
        )

    def _load_subcategories(self, category: str) -> list[str]:
        """
        Load subcategories for a given category.

        Args:
            category (str): Category name.

        Raises:
            ValueError: If no subcategories are found for the given category.

        Returns:
            list[str]: List of subcategories.
        """
        key = category.lower().replace(" ", "_")
        try:
            return SUBCATEGORIES[key]
        except KeyError as exc:
            raise ValueError(
                f"No subcategories found for category '{category}'"
            ) from exc

    def _load_or_build_embeddings(self, rebuild: bool) -> np.ndarray:
        """
        Load or build subcategory response embeddings.

        Args:
            rebuild (bool): Whether to rebuild embeddings even if cached ones exist.

        Raises:
            ValueError: If the embeddings file is missing expected data.

        Returns:
            np.ndarray: Array of subcategory embeddings.
        """
        if self.embeddings_path.exists() and not rebuild:
            data = np.load(self.embeddings_path, allow_pickle=True)
            if isinstance(data, np.lib.npyio.NpzFile):
                vectors = data.get("vectors")
                subs = data.get("subcategories")
                if vectors is None:
                    raise ValueError("Embeddings file missing 'vectors'")
                if subs is not None and len(subs) != len(self.subcategories):
                    logger.warning("Subcategory count mismatch; rebuilding embeddings")
                else:
                    return vectors
            else:
                return data

        logger.info("Building response embeddings for subcategories")

        # Apply the same normalization used in notebooks: replace underscores, then encoder normalize.
        normalized = [self._normalize_subcategory(sub) for sub in self.subcategories]
        vectors = self.encoder.batch_encode(
            normalized,
            encoder_type="response_encoder",
            batch_size=self.batch_size,
        )

        np.savez(
            self.embeddings_path,
            vectors=vectors,
            subcategories=self.subcategories,
        )
        logger.info(f"Saved response embeddings to {self.embeddings_path}")

        return vectors

    def _normalize_subcategory(self, name: str) -> str:
        """
        Normalize subcategory strings for stable embeddings.

        Args:
            name (str): Subcategory name.

        Returns:
            str: Normalized subcategory name.
        """

        name = name.replace("_", " ")

        return self.encoder.normalize_text(name)

    def _combine_scores(
        self, sim_scores: np.ndarray, bm25_scores: np.ndarray
    ) -> np.ndarray:
        """
        Combine similarity and BM25 scores.

        Args:
            sim_scores (np.ndarray): Similarity scores.
            bm25_scores (np.ndarray): BM25 scores.

        Returns:
            np.ndarray: Combined scores.
        """
        if self.bm25_weight <= 0:
            return sim_scores

        bm25_max = bm25_scores.max() if bm25_scores.size else 0.0
        sim_max = sim_scores.max() if sim_scores.size else 0.0

        bm25_norm = (
            bm25_scores / (bm25_max + 1e-9)
            if bm25_max > 0
            else np.zeros_like(bm25_scores)
        )

        sim_norm = (
            sim_scores / (sim_max + 1e-9) if sim_max > 0 else np.zeros_like(sim_scores)
        )

        return self.bm25_weight * bm25_norm + (1 - self.bm25_weight) * sim_norm

    def retrieve(self, text: str, top_k: int = 10) -> list[str]:
        """
        Retrieve top-k subcategories for a given text.

        Args:
            text (str): Input text.
            top_k (int, optional): Number of top subcategories to retrieve. Defaults to 10.

        Returns:
            list[str]: List of top-k subcategories.
        """
        return self.batch_retrieve([text], top_k=top_k)[0]

    def batch_retrieve(self, texts: Iterable[str], top_k: int = 10) -> list[list[str]]:
        """
        Batch retrieve top-k subcategories for given texts.

        Args:
            texts (Iterable[str]): Input texts.
            top_k (int, optional): Number of top subcategories to retrieve. Defaults to 10.

        Returns:
            list[list[str]]: List of lists of top-k subcategories for each input text.
        """
        texts = list(texts)
        if not texts:
            return []

        query_vectors = self.encoder.batch_encode(
            texts, encoder_type="question_encoder", batch_size=self.batch_size
        )
        similarity = np.inner(query_vectors, self.response_vectors)
        k = min(top_k, similarity.shape[1])

        results = []
        for idx, text in enumerate(texts):
            sim_scores = similarity[idx]

            if self.bm25 and self.bm25_weight > 0:
                bm25_scores = self.bm25.score_vector(text)
                combined = self._combine_scores(sim_scores, bm25_scores)
            else:
                combined = sim_scores

            top_indices = np.argsort(-combined)[:k]
            results.append([self.subcategories[i] for i in top_indices])

        return results

    def __call__(self, item: DataItem) -> DataItem:
        """
        Apply subcategorization to entities in the data item.

        Args:
            item (DataItem): Input data item.

        Returns:
            DataItem: Data item with added subclass labels.
        """
        item = deepcopy(item)
        ents = get_element(item, levels=["predictions", "entities"]) or []
        texts = [ent["text"] for ent in ents]
        filtered_ents = filter_by_category(ents, self.category)
        retrieved = self.batch_retrieve(texts, top_k=5)

        for ent, retrieved_ in zip(ents, retrieved):
            if ent in filtered_ents and not get_element(
                ent, levels=["attrs", "aymurai_label_subclass"]
            ):
                ent.setdefault("attrs", {})["aymurai_label_subclass"] = retrieved_

        item.setdefault("predictions", {})["entities"] = ents

        return item
