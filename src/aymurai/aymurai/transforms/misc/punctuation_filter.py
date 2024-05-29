from copy import deepcopy
from string import punctuation

from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element
from aymurai.meta.pipeline_interfaces import Transform


class PunctuationFilter(Transform):
    "transform to filter out predictions that are punctuation marks"

    def __call__(self, item: DataItem) -> DataItem:
        item = deepcopy(item)

        ents = get_element(item, levels=["predictions", "entities"]) or []
        filtered_ents = [ent for ent in ents if ent["text"] not in punctuation]
        item["predictions"]["entities"] = filtered_ents

        return item
