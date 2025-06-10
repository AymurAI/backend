from copy import deepcopy

from aymurai.meta.pipeline_interfaces import Transform
from aymurai.meta.types import DataItem


class DummyAnnotToPred(Transform):
    """dummy transform to convert annotations into predictions"""

    def __call__(self, item: DataItem) -> DataItem:
        item = deepcopy(item)
        if "annotations" not in item:
            return item
        item["predictions"] = {"entities": item["annotations"]["entities"]}
        return item
