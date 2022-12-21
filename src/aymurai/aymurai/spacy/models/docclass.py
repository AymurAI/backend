from pathlib import Path
from typing import Union

from aymurai.logging import get_logger
from aymurai.spacy.models.core import SpacyModel
from aymurai.meta.types import DataItem, DataBlock

logger = get_logger(__name__)


class SpacyMultiLabelDocClassifier(SpacyModel):
    def __init__(
        self,
        base_config: Union[str, Path] = "doc-catsifier",
        pretraining: bool = True,
        device: str = "gpu",
        dataset_cache: bool = True,
        batch_size: int = 64,
        categories: list[str] = [],
    ):
        assert categories, "categories cannot be empty"

        super().__init__(
            base_config=base_config,
            pretraining=pretraining,
            device=device,
            dataset_cache=dataset_cache,
            batch_size=batch_size,
            categories=categories,
        )

    def predict(self, data: DataBlock) -> DataBlock:
        pass

    def single_predict(self, item: DataItem) -> DataItem:
        pass
