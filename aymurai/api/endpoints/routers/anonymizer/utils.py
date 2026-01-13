import re
import unicodedata
from collections import Counter
from typing import Iterable

from rapidfuzz import process
from rapidfuzz.fuzz import (
    WRatio,
    partial_ratio,
    partial_token_set_ratio,
    partial_token_sort_ratio,
    ratio,
    token_set_ratio,
    token_sort_ratio,
)

from aymurai.meta.api_interfaces import DocLabel
from aymurai.meta.entities import CanonicalEntity

__all__ = [
    "SCORER_MAP",
    "PROCESSOR_MAP",
    "build_canonical_entities",
    "resolve_processor",
]

SCORER_MAP = {
    "ratio": ratio,
    "partial_ratio": partial_ratio,
    "token_sort_ratio": token_sort_ratio,
    "token_set_ratio": token_set_ratio,
    "partial_token_set_ratio": partial_token_set_ratio,
    "partial_token_sort_ratio": partial_token_sort_ratio,
    "wratio": WRatio,
}

PROCESSOR_MAP = {
    "none": None,
    "light_normalizer": "light_normalizer",
    "hard_normalizer": "hard_normalizer",
    "legal_text_normalizer": "legal_text_normalizer",
}


def hard_normalizer(text: str) -> str:
    if not text:
        return ""

    normalized = "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    normalized = re.sub(r"[.,\-]", " ", normalized)
    normalized = " ".join(normalized.lower().split())
    return normalized


def light_normalizer(text: str) -> str:
    return text.lower().strip() if text else ""


def legal_text_normalizer(text: str) -> str:
    if not text:
        return ""

    normalized = "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    normalized = normalized.lower()

    legal_titles = r"\b(dr|dra|sr|sra|expte|nro|no|pcia)\b\.?"
    normalized = re.sub(legal_titles, "", normalized)

    stopwords = r"\b(de|del|la|las|el|los|y|en)\b"
    normalized = re.sub(stopwords, "", normalized)
    normalized = re.sub(r"[^\w\s]", "", normalized)

    return " ".join(normalized.split())


def resolve_processor(name: str) -> callable | None:
    key = name.lower()
    mapped = PROCESSOR_MAP.get(key)
    if mapped is None:
        return None
    if mapped == "light_normalizer":
        return light_normalizer
    if mapped == "hard_normalizer":
        return hard_normalizer
    if mapped == "legal_text_normalizer":
        return legal_text_normalizer
    return None


def cluster_with_cdist(
    *,
    items: list[dict[str, str]],
    threshold: int,
    scorer: callable,
    processor: callable | None,
) -> list[list[tuple[str, str, str]]]:
    if not items:
        return []

    entities = [item.get("text", "") for item in items]
    labels = [item.get("aymurai_label", "UNKNOWN") for item in items]

    if processor:
        normed = [processor(entity) for entity in entities]
    else:
        normed = [str(entity) for entity in entities]

    sim = process.cdist(normed, normed, scorer=scorer, score_cutoff=threshold)

    parent = list(range(len(normed)))

    def find(idx: int) -> int:
        if parent[idx] == idx:
            return idx
        parent[idx] = find(parent[idx])
        return parent[idx]

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    n = len(normed)
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i][j] >= threshold:
                union(i, j)

    clusters_map: dict[int, list[tuple[str, str, str]]] = {}
    for idx in range(n):
        root = find(idx)
        clusters_map.setdefault(root, []).append(
            (entities[idx], normed[idx], labels[idx])
        )

    return list(clusters_map.values())


def parse_item(item: tuple[str, str, str]) -> tuple[str, str, str]:
    orig, norm, label = item
    return label, orig, norm


def pick_cluster_label(parsed_items: list[tuple[str, str, str]]) -> str:
    labels = [label for label, _, _ in parsed_items]
    return Counter(labels).most_common(1)[0][0]


def pick_canonical_text(parsed_items: list[tuple[str, str, str]]) -> str:
    return max(parsed_items, key=lambda item: len(item[1]))[1]


def clusters_to_canonical_entities(
    clusters: list[list[tuple[str, str, str]]],
) -> list[CanonicalEntity]:
    canonical_entities = []
    for cluster in clusters:
        parsed = [parse_item(item) for item in cluster]
        label = pick_cluster_label(parsed)
        canonical_text = pick_canonical_text(parsed)
        aliases = sorted({orig for _, orig, _ in parsed})
        canonical_entities.append(
            CanonicalEntity(
                aymurai_label=label,
                canonical_text=canonical_text,
                aliases=aliases,
                attributes={},
                relations=[],
            )
        )
    return canonical_entities


def build_canonical_entities(
    labels: Iterable[DocLabel],
    *,
    target_labels: set[str] | None = None,
    threshold: int,
    scorer: callable,
    processor: callable | None,
) -> list[CanonicalEntity]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for label in labels:
        attrs = label.attrs
        if not attrs or not attrs.aymurai_label:
            continue
        if target_labels and attrs.aymurai_label not in target_labels:
            continue
        alias = attrs.aymurai_alt_text or label.text
        grouped.setdefault(attrs.aymurai_label, []).append(
            {"text": alias, "aymurai_label": attrs.aymurai_label}
        )

    canonical_entities = []
    for items in grouped.values():
        clusters = cluster_with_cdist(
            items=items,
            threshold=threshold,
            scorer=scorer,
            processor=processor,
        )
        canonical_entities.extend(clusters_to_canonical_entities(clusters))

    return canonical_entities
