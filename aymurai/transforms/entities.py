from copy import deepcopy

from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element
from aymurai.meta.pipeline_interfaces import Transform

# class FilterEntity(Transform):
#     def __init__(self, entities: list[str], field: str = "predictions"):
#         self.entities = entities
#         self.field = field

#     def __call__(self, item: DataItem) -> DataItem:
#         item = deepcopy(item)

#         data_ents = get_element(item, [self.field, "entities"])
#         if data_ents:
#             data_ents = filter(lambda x: x["label"] not in self.entities, data_ents)
#             item[self.field]["entities"] = list(data_ents)

#         return item


class FilterEntity(Transform):
    def __init__(
        self,
        enable: list[str] = [],
        disable: list[str] = [],
        field: str = "predictions",
    ):
        self.enable = enable
        self.disable = disable
        self.field = field

        msg_ = "you must select only an enable or disable list but not both."
        assert not (len(enable) and len(disable)), msg_

    def __call__(self, item: DataItem) -> DataItem:
        item = deepcopy(item)

        ents = get_element(item, [self.field, "entities"])
        if not ents:
            return item

        if self.enable:
            ents = filter(lambda x: x["label"] in self.enable, ents)
        if self.disable:
            ents = filter(lambda x: x["label"] not in self.disable, ents)

        item[self.field]["entities"] = list(ents)

        return item


class EntityToSpans(Transform):
    def __init__(self, field: str = "predictions", span_key: str = "sc"):
        self.field = field
        self.span_key = span_key

    def __call__(self, item: DataItem) -> DataItem:
        item = deepcopy(item)

        ents = get_element(item, [self.field, "entities"]) or []

        if not ents:
            return item

        # copy the spans that already exists
        item[self.field]["spans"] = get_element(item, [self.field, "spans"]) or {}

        # overwrite span_key with new ents
        item[self.field]["spans"][self.span_key] = list(ents)

        return item
