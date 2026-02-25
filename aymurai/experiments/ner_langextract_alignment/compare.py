from __future__ import annotations

from collections import defaultdict

from aymurai.experiments.ner_langextract_alignment.types import (
    ComparisonResult,
    NormalizedEntity,
)


def compare_entities(
    ner_entities: list[NormalizedEntity],
    langextract_entities: list[NormalizedEntity],
) -> ComparisonResult:
    ner_map: dict[tuple, list[NormalizedEntity]] = defaultdict(list)
    lx_map: dict[tuple, list[NormalizedEntity]] = defaultdict(list)

    for ent in ner_entities:
        ner_map[(ent.label, ent.start_char, ent.end_char, ent.text)].append(ent)
    for ent in langextract_entities:
        lx_map[(ent.label, ent.start_char, ent.end_char, ent.text)].append(ent)

    exact_match: list[NormalizedEntity] = []
    partial_match: list[NormalizedEntity] = []
    only_in_ner: list[NormalizedEntity] = []
    only_in_langextract: list[NormalizedEntity] = []

    keys = set(ner_map.keys()) | set(lx_map.keys())

    for key in sorted(keys):
        ner_items = ner_map.get(key, [])
        lx_items = lx_map.get(key, [])
        n_match = min(len(ner_items), len(lx_items))

        exact_match.extend(ner_items[:n_match])

        if len(ner_items) > n_match:
            only_in_ner.extend(ner_items[n_match:])
        if len(lx_items) > n_match:
            only_in_langextract.extend(lx_items[n_match:])

    for ner_ent in ner_entities:
        for lx_ent in langextract_entities:
            if (
                lx_ent.text != ner_ent.text
                and lx_ent.text in ner_ent.text
                and ner_ent.label == lx_ent.label
            ):
                partial_match.append(ner_ent)

    if not only_in_ner and not only_in_langextract:
        status = "exact_match"
    elif only_in_ner and not only_in_langextract:
        status = "ner_only"
    elif only_in_langextract and not only_in_ner:
        status = "langextract_only"
    elif partial_match:
        status = "partial_match"
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
