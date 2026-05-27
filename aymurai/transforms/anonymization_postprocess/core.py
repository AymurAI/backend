import re
from copy import deepcopy

from aymurai.meta.pipeline_interfaces import Transform
from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element
from aymurai.transforms.anonymization_postprocess.exact_labels import EXACT_LABELS


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
        label = ent["attrs"]["aymurai_label"]

        # Match leading and trailing non-alphanumeric characters
        leading_match = re.match(r"^\W+", original_text)
        trailing_match = re.search(r"\W+$", original_text)

        # Calculate the number of characters to remove
        leading_chars_removed = len(leading_match.group()) if leading_match else 0
        trailing_chars_removed = len(trailing_match.group()) if trailing_match else 0

        # Clean the text
        cleaned_text = pattern.sub("", original_text)

        if not cleaned_text:
            return None

        raw_subclass = ent["attrs"]["aymurai_label_subclass"]
        if isinstance(raw_subclass, list):
            aymurai_label_subclass = raw_subclass.copy()
        elif raw_subclass:
            aymurai_label_subclass = [raw_subclass]
        else:
            aymurai_label_subclass = []

        if label in EXACT_LABELS:
            flattened_text = re.sub(r"[^a-zA-Z0-9]", "", cleaned_text)
            if flattened_text and flattened_text not in aymurai_label_subclass:
                aymurai_label_subclass.append(flattened_text)

        # Update the entity's alt text and indices
        ent["attrs"]["aymurai_alt_text"] = cleaned_text
        ent["attrs"]["aymurai_alt_start_char"] = start_char + leading_chars_removed
        ent["attrs"]["aymurai_alt_end_char"] = end_char - trailing_chars_removed
        ent["attrs"]["aymurai_label_subclass"] = aymurai_label_subclass

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

        # Filter out predictions with empty alt text and update the rest
        item[self.field]["entities"] = [
            out for ent in ents if (out := self.process(ent)) is not None
        ]

        return item
