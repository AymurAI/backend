import re
from copy import deepcopy

from aymurai.meta.types import DataItem
from aymurai.meta.pipeline_interfaces import Transform


class FlairTextNormalize(Transform):
    def __call__(self, item: DataItem) -> DataItem:
        item = deepcopy(item)

        doc = item["data"]["doc.text"]

        # replace '\t' and '\xa0' for white space
        doc = re.sub(r"(?:\t|\xa0)+", " ", doc)
        # remove multiple spaces except new lines
        doc = re.sub(r"[^\S\r\n]+", " ", doc)
        # replace multiple new lines with just one break
        doc = re.sub(r"\n+", "\n", doc)

        item["data"]["doc.text"] = doc

        return item
