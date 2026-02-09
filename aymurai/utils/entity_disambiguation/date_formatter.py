from aymurai.transforms.datetime_formatter import DatetimeFormatter
from aymurai.meta.api_interfaces import DocLabel
from aymurai.meta.entities import CanonicalEntity


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

        day_month_key = norm_date[:5] if norm_date is not None else norm_date

        if day_month_key not in groups:
            groups[day_month_key] = CanonicalEntity(
                aymurai_label="FECHA",
                canonical_text=raw_date,
                aliases=[],
                attributes={},
            )

        if day_month_key in groups and raw_date not in groups[day_month_key].aliases:
            groups[day_month_key].aliases.append(raw_date)
            groups[day_month_key].attributes["norm_date"] = raw_date

        label.attrs.canonical_entity_id = groups[day_month_key].entity_id

    return list(groups.values())
