import re
from copy import deepcopy

from aymurai.meta.pipeline_interfaces import Transform
from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element


class AnonymizationEntityCleaner(Transform):
    def __init__(self, field: str = "predictions"):
        """
        Args:
            field (str, optional): field with entities. Defaults to "predictions".
        """
        self.field = field

    def process(self, ent):
        """
        Post processing function to clear non-alphanumeric characters from prediction
        start and end

        Args:
            ent (dict): entity to process

        Returns:
            dict: processed entity
        """

        pattern = re.compile(r"^\W+|\W+$")

        text = ent["text"]
        ent["attrs"]["aymurai_alt_text"] = pattern.sub("", text)
        return ent

    def __call__(self, item: DataItem) -> DataItem:
        """
        Args:
            item (DataItem): item to process

        Returns:
            DataItem: processed item
        """
        item = deepcopy(item)

        ents = get_element(item, [self.field, "entities"]) or []
        ents = [self.process(ent) for ent in ents]

        return item
