import re
from copy import deepcopy

from aymurai.meta.types import DataItem
from aymurai.meta.pipeline_interfaces import Transform


class FlairTextNormalize(Transform):
    """
    Normalize text for Flair
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        # replace '\t' and '\xa0' for white space
        text = re.sub(r"(?:\t|\xa0)+", " ", text)

        # remove multiple spaces except new lines
        text = re.sub(r"[^\S\r\n]+", " ", text)

        # replace multiple new lines with just one break
        text = re.sub(r"\n+", "\n", text)

        return text

    def __call__(self, item: DataItem) -> DataItem:
        item = deepcopy(item)

        doc = item["data"]["doc.text"]
        doc = self.normalize_text(doc)

        item["data"]["doc.text"] = doc

        return item
