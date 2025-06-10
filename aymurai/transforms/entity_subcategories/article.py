from copy import deepcopy

from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element
from aymurai.meta.pipeline_interfaces import Transform
from aymurai.transforms.entity_subcategories.utils import (
    filter_by_category,
    map_article_to_code_or_law,
)


class ArticleSubcategorizer(Transform):
    """
    Find subcategories using regex patterns
    """

    def __call__(self, item: DataItem) -> DataItem:
        item = deepcopy(item)

        ents = get_element(item, levels=["predictions", "entities"]) or []
        texts = map(lambda x: x["text"], ents)

        filtered_ents = filter_by_category(ents, "ART_INFRINGIDO")
        found_subcats = list(map(lambda x: map_article_to_code_or_law(x, ents), texts))

        for ent, found_subcat in zip(ents, found_subcats):
            if ent in filtered_ents and not get_element(
                ent, levels=["attrs", "aymurai_label_subclass"]
            ):
                ent["attrs"]["aymurai_label_subclass"] = found_subcat

        item["predictions"]["entities"] = ents

        return item
