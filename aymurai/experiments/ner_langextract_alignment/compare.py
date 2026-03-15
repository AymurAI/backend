from __future__ import annotations

from collections import defaultdict

from aymurai.experiments.ner_langextract_alignment.types import (
    ComparisonResult,
    NormalizedEntity,
)


def _comparison_text(entity: NormalizedEntity) -> str:
    return str(entity.normalized_text or entity.text or "")


def compare_entities(
    ner_entities: list[NormalizedEntity],
    langextract_entities: list[NormalizedEntity],
) -> ComparisonResult:
    ner_map: dict[tuple, list[NormalizedEntity]] = defaultdict(list)
    lx_map: dict[tuple, list[NormalizedEntity]] = defaultdict(list)

    for ent in ner_entities:
        ner_map[(ent.key())].append(ent)
    for ent in langextract_entities:
        lx_map[(ent.key())].append(ent)

    exact_match: list[NormalizedEntity] = []
    remaining_ner: list[NormalizedEntity] = []
    remaining_lx: list[NormalizedEntity] = []

    all_exact_keys = set(ner_map.keys()) | set(lx_map.keys())
    for key in all_exact_keys:
        ner_items = ner_map.get(key, [])
        lx_items = lx_map.get(key, [])
        n_match = min(len(ner_items), len(lx_items))
        exact_match.extend(ner_items[:n_match])

        if len(ner_items) > n_match:
            remaining_ner.extend(ner_items[n_match:])
        if len(lx_items) > n_match:
            remaining_lx.extend(lx_items[n_match:])

    partial_match: list[NormalizedEntity] = []
    matched_in_remaining_lx = set()
    matched_in_remaining_ner = set()

    for ner_ent in remaining_ner:
        for lx_ent in remaining_lx:
            ner_text = _comparison_text(ner_ent)
            lx_text = _comparison_text(lx_ent)
            if ner_ent.label == lx_ent.label and lx_text and lx_text in ner_text:
                partial_match.append(ner_ent)
                matched_in_remaining_ner.add(id(ner_ent))
                matched_in_remaining_lx.add(id(lx_ent))
                break

    only_in_ner: list[NormalizedEntity] = [
        e for e in remaining_ner if id(e) not in matched_in_remaining_ner
    ]
    only_in_langextract: list[NormalizedEntity] = [
        e for e in remaining_lx if id(e) not in matched_in_remaining_lx
    ]

    if not remaining_ner and not remaining_lx:
        status = "exact_match"
    elif (
        partial_match
        and not exact_match
        and not only_in_ner
        and not only_in_langextract
    ):
        status = "partial_match"
    elif (
        only_in_ner
        and not only_in_langextract
        and not exact_match
        and not partial_match
    ):
        status = "ner_only"
    elif (
        only_in_langextract
        and not only_in_ner
        and not exact_match
        and not partial_match
    ):
        status = "langextract_only"
    else:
        status = "mixed"

    return ComparisonResult(
        status=status,
        exact_match=exact_match,
        partial_match=partial_match,
        only_in_ner=only_in_ner,
        only_in_langextract=only_in_langextract,
    )


def status_distribution(samples: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {
        "exact_match": 0,
        "ner_only": 0,
        "langextract_only": 0,
        "partial_match": 0,
        "mixed": 0,
    }
    for sample in samples:
        status = sample.get("comparison", {}).get("status")
        if status in out:
            out[status] += 1
    return out
