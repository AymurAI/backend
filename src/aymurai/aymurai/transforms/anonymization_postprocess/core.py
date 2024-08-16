import re
from copy import deepcopy
from string import punctuation

from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element
from aymurai.meta.pipeline_interfaces import Transform


class AnonymizationEntityCleaner(Transform):
    def __init__(self, field: str = "predictions"):
        """
        Args:
            field (str, optional): field with entities. Defaults to "predictions".
        """
        self.field = field

    def process(self, ent: dict) -> dict:
        """
        Post processing function to clear non-alphanumeric characters from prediction
        start and end, update alternative text, and adjust start and end indices.

        Args:
            ent (dict): entity to process

        Returns:
            dict: processed entity
        """
        # Define the regex pattern
        pattern = re.compile(r"^\W+|\W+$")

        # Get the original text and start and end indices
        original_text = ent["text"]
        start_char = ent["start_char"]
        end_char = ent["end_char"]

        # Match leading and trailing non-alphanumeric characters
        leading_match = re.match(r"^\W+", original_text)
        trailing_match = re.search(r"\W+$", original_text)

        # Calculate the number of characters to remove
        leading_chars_removed = len(leading_match.group()) if leading_match else 0
        trailing_chars_removed = len(trailing_match.group()) if trailing_match else 0

        # Clean the text
        cleaned_text = pattern.sub("", original_text)

        # Update the entity's alt text and indices
        ent["attrs"]["aymurai_alt_text"] = cleaned_text
        ent["attrs"]["aymurai_alt_start_char"] = start_char + leading_chars_removed
        ent["attrs"]["aymurai_alt_end_char"] = end_char - trailing_chars_removed

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

        # Filter out predictions that are punctuation marks only
        ents = [ent for ent in ents if ent["text"] not in punctuation]
        ents = [self.process(ent) for ent in ents]

        return item
