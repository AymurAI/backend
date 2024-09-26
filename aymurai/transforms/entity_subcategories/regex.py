from copy import deepcopy

from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element
from aymurai.meta.pipeline_interfaces import Transform

from .patterns import regex_patterns
from .utils import find_subcategories


class RegexSubcategorizer(Transform):
    """
    Find subcategories using regex patterns
    """

    NEED_CONTEXT = ["PERSONA_ACUSADA_NO_DETERMINADA", "NOMBRE"]

    def __call__(self, item: DataItem) -> DataItem:
        """
        Regex subcategorizer by patterns

        Args:
            item (DataItem): item to process

        Returns:
            DataItem: processed item
        """
        item = deepcopy(item)

        ents = get_element(item, levels=["predictions", "entities"]) or []

        for category, patterns in regex_patterns.items():
            use_context = True if category in self.NEED_CONTEXT else False
            ents = find_subcategories(ents, category, patterns, use_context=use_context)

        item["predictions"]["entities"] = ents

        return item
