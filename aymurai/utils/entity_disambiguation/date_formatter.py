from aymurai.meta.api_interfaces import DocLabel
from aymurai.meta.entities import CanonicalEntity
import uuid


def get_canonical_dates(labels: list[DocLabel]) -> list[CanonicalEntity]:
    """
    Groups date labels by their normalized day and month (if available) to create canonical entities.

    Args:
        labels (list[DocLabel]): A list of document labels to process.

    Returns:
        list[CanonicalEntity]: A list of canonical entities representing unique dates,
            each with its aliases and attributes.
    """
    groups = {}

    for label in labels:
        if label.attrs.aymurai_label != "FECHA":
            continue

        raw_date = label.attrs.aymurai_alt_text or label.text

        norm_date = (
            max(label.attrs.aymurai_label_subclass)
            if label.attrs.aymurai_label_subclass
            else None
        )

        if norm_date:
            parts = norm_date.split("/")
            day = parts[0]
            month = parts[1]
            year = parts[2] if len(parts) > 2 else "1900"
            if year == "1900":
                day_month_key = f"{day}/{month}"
            else:
                day_month_key = f"{day}/{month}/{year}"
        else:
            day_month_key = uuid.uuid4()

        if day_month_key not in groups:
            groups[day_month_key] = CanonicalEntity(
                aymurai_label="FECHA",
                canonical_text=raw_date,
                aliases=[],
                attributes={},
            )

        if day_month_key in groups and raw_date not in groups[day_month_key].aliases:
            groups[day_month_key].aliases.append(raw_date)

        label.attrs.canonical_entity_id = groups[day_month_key].entity_id

    return list(groups.values())
