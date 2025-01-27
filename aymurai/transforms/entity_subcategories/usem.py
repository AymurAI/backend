import os
from hashlib import md5
from copy import deepcopy

import numpy as np
import tensorflow as tf

from aymurai.logger import get_logger
from aymurai.meta.types import DataItem
from aymurai.models.usem.core import USEMQA
from aymurai.utils.download import download
from aymurai.utils.misc import is_url, get_element
from aymurai.meta.pipeline_interfaces import Transform

from .utils import filter_by_category

logger = get_logger(__name__)


class USEMSubcategorizer(Transform):
    """
    Use USEM to retrieve subcategories
    """

    usem = USEMQA()

    def __init__(
        self,
        category: str,
        subcategories_path: list[str],
        response_embeddings_path: str,
        device: str = "/cpu:0",
    ):
        """
        Sentence Similarity using USEM (Universal Sentence Encoder Multilingual QA)

        Args:
            category (str): category to filter
            subcategories_path (list[str]): path to subcategories
            response_embeddings_path (str): path to response embeddings
            device (str, optional): device to use. Defaults to "/cpu:0".
        """
        self.category = category

        CACHE_PATH = os.path.join(
            os.getenv("AYMURAI_CACHE_BASEPATH", "/resources/cache/aymurai"),
            self.__name__,
        )

        logger.info(f"load usem options from {subcategories_path}")
        if is_url(url := subcategories_path):
            fname = md5(url.encode("utf-8")).hexdigest()
            subcategories_path = f"{CACHE_PATH}/{fname}"
            logger.info(f"downloading options on {subcategories_path}")
            os.makedirs(CACHE_PATH, exist_ok=True)
            subcategories_path = download(url, output=subcategories_path)

        with open(subcategories_path, "r") as file:
            self.subcategories = file.read().splitlines()
        logger.info(f"options head: {self.subcategories[:5]}")

        # download embeddings
        if is_url(url := response_embeddings_path):
            fname = md5(url.encode("utf-8")).hexdigest()
            model_path = f"{CACHE_PATH}/{fname}"
            logger.info(f"downloading embeddings on {model_path}")
            os.makedirs(CACHE_PATH, exist_ok=True)
            response_embeddings_path = download(url, output=model_path)
        logger.info(f"load usem embeddings from {response_embeddings_path}")
        self.usem_vectors = self.load_usem_vectors(response_embeddings_path)
        self.device = device

    def load_usem_vectors(self, file_path):
        """
        Load USEM vectors
        """
        usem_vectors = np.load(file_path)
        return usem_vectors.copy()

    def retrieve(self, text: str, top_k: int = 10) -> list[str]:
        """
        Retrieve similar sentences using USEM
        """
        with tf.device(self.device):
            query_vector = self.usem.encode(
                [text],
                encoder_type="question_encoder",
            )

        products = np.inner(query_vector, self.usem_vectors)[0]
        similar_idx = np.flip(products.argsort())[:top_k]
        similar_sentences = [self.subcategories[idx] for idx in similar_idx]

        return similar_sentences

    def __call__(self, item: DataItem) -> DataItem:
        """
        Retrieve subcategories for entities. If the entity is not in the category of interest,
        the subcategory is not retrieved.

        Args:
            item (DataItem): input data item

        Returns:
            DataItem: output data item
        """
        item = deepcopy(item)

        ents = get_element(item, levels=["predictions", "entities"]) or []

        texts = list(map(lambda x: x["text"], ents))
        filtered_ents = filter_by_category(ents, self.category)
        retrieved = list(map(self.retrieve, texts))

        for ent, retrieved_ in zip(ents, retrieved):
            if ent in filtered_ents and not get_element(
                ent, levels=["attrs", "aymurai_label_subclass"]
            ):
                ent["attrs"]["aymurai_label_subclass"] = retrieved_

        item["predictions"]["entities"] = ents

        return item
