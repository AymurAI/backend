from aymurai.api.endpoints.routers.anonymizer.utils import (
    SCORER_MAP,
    build_canonical_entities,
    resolve_processor,
)

from aymurai.meta.api_interfaces import (
    DocumentAnnotations,
)
from aymurai.meta.entities import CanonicalEntities


def pre_cluster(
    paragraphs: list[dict],
    target_labels: list[str] = None,
    threshold: int = 70,
    scorer: str = "token_set_ratio",
    processor: str = "light_normalizer",
) -> CanonicalEntities:

    scorer = SCORER_MAP.get(scorer.lower())
    processor = resolve_processor(processor)

    predictions = DocumentAnnotations(data=paragraphs)

    labels = [
        label for paragraph in predictions.data for label in (paragraph.labels or [])
    ]

    target_set = {label.strip() for label in target_labels} if target_labels else None

    canonical_entities = build_canonical_entities(
        labels,
        target_labels=target_set,
        threshold=threshold,
        scorer=scorer,
        processor=processor,
    )

    return canonical_entities
