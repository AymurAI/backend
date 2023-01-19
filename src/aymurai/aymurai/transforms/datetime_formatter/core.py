from copy import deepcopy

from datetime_matcher import DatetimeMatcher

from aymurai.meta.types import DataItem
from aymurai.utils.misc import get_element
from aymurai.meta.pipeline_interfaces import Transform

from .patterns import patterns


class DatetimeFormatter(Transform):
    def __init__(self, field: str = "predictions"):
        self.field = field
        self.dtm = DatetimeMatcher()
        self.VALID_ENTS = list(patterns.keys())

        self.day0 = self.dtm.extract_datetime("%H:%M", "00:00")

    def process(self, ent):
        if (label := ent["label"]) not in self.VALID_ENTS:
            return ent

        pats = patterns.get(label, [])
        suggestions = []
        for pat in pats:
            datetime = self.dtm.extract_datetime(pat, ent["text"])
            if not datetime:
                continue

            diff = datetime - self.day0
            # not a date, handle just as time
            if diff.days == 0:
                text_repr = datetime.strftime("%H:%M")
            # handle it has date
            else:
                text_repr = datetime.strftime("%d/%m/%Y")
            suggestions.append(text_repr)

        ent["attrs"]["aymurai_label_subclass"] = suggestions

        return ent

    def __call__(self, item: DataItem) -> DataItem:
        item = deepcopy(item)

        ents = get_element(item, [self.field, "entities"]) or []
        ents = [self.process(ent) for ent in ents]

        return item
