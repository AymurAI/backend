import re
from copy import deepcopy
from string import punctuation

from aymurai.meta.pipeline_interfaces import Transform
from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element

_ENTITY_BOUNDARY_PATTERN = re.compile(r"^\W+|\W+$")
from aymurai.transforms.anonymization_postprocess.exact_labels import EXACT_LABELS


def clean_entity_boundaries(
    text: str,
    *,
    start_char: int,
    end_char: int,
) -> dict[str, int | str] | None:
    """
    Cleans the boundaries of an entity by removing leading and trailing non-alphanumeric characters.

    Args:
        text (str): The text of the entity.
        start_char (int): The starting character index of the entity.
        end_char (int): The ending character index of the entity.

    Returns:
        dict[str, int | str] | None: A dictionary with the cleaned text and updated character indices,
            or None if the cleaned text is empty.
    """
    original_text = str(text or "")

    leading_match = re.match(r"^\W+", original_text)
    trailing_match = re.search(r"\W+$", original_text)

    leading_chars_removed = len(leading_match.group()) if leading_match else 0
    trailing_chars_removed = len(trailing_match.group()) if trailing_match else 0
    cleaned_text = _ENTITY_BOUNDARY_PATTERN.sub("", original_text)

    if not cleaned_text:
        return None

    return {
        "text": cleaned_text,
        "start_char": int(start_char) + leading_chars_removed,
        "end_char": int(end_char) - trailing_chars_removed,
    }


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
        cleaned = clean_entity_boundaries(
            ent["text"],
            start_char=ent["start_char"],
            end_char=ent["end_char"],
        )
        if cleaned is None:
            return ent

        label = ent["attrs"]["aymurai_label"]
        raw_subclass = ent["attrs"]["aymurai_label_subclass"]

        if isinstance(raw_subclass, list):
            aymurai_label_subclass = raw_subclass.copy()
        elif raw_subclass:
            aymurai_label_subclass = [raw_subclass]
        else:
            aymurai_label_subclass = []

        if label in EXACT_LABELS:
            flattened_text = re.sub(r"[^a-zA-Z0-9]", "", cleaned["text"])
            if flattened_text and flattened_text not in aymurai_label_subclass:
                aymurai_label_subclass.append(flattened_text)

        ent["attrs"]["aymurai_alt_text"] = cleaned["text"]
        ent["attrs"]["aymurai_alt_start_char"] = cleaned["start_char"]
        ent["attrs"]["aymurai_alt_end_char"] = cleaned["end_char"]
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
