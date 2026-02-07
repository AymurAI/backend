from aymurai.transforms.datetime_formatter import DatetimeFormatter
from aymurai.meta.api_interfaces import DocLabel
from aymurai.meta.entities import CanonicalEntity

import locale

original_setlocale = locale.setlocale
locale.setlocale = lambda *args, **kwargs: "C"

try:
    from aymurai.transforms.datetime_formatter.core import DatetimeFormatter
except Exception as e:
    print(f"Error importing DatetimeFormatter: {e}")
finally:
    locale.setlocale = original_setlocale

formatter = DatetimeFormatter()


def get_canonical_dates(labels: list[DocLabel]) -> list[CanonicalEntity]:
    groups = {}

    for label in labels:
        if label.attrs.aymurai_label != "FECHA":
            continue

        raw_date = label.attrs.aymurai_alt_text or label.text

        label_processed = formatter.process(label)

        norm_date = (
            label_processed.attrs.aymurai_label_subclass[0]
            if label_processed.attrs.aymurai_label_subclass
            else None
        )

        if norm_date not in groups:
            groups[norm_date] = CanonicalEntity(
                aymurai_label="FECHA",
                canonical_text=raw_date,
                aliases=[],
                attributes={},
            )
        if norm_date in groups and raw_date not in groups[norm_date].aliases:
            groups[norm_date].aliases.append(raw_date)

        label.attrs.canonical_entity_id = groups[norm_date].entity_id

    return list(groups.values())
