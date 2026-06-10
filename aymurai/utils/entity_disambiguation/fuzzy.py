from collections import Counter
from typing import Iterable

from rapidfuzz import process
from rapidfuzz.fuzz import token_set_ratio

from aymurai.meta.api_interfaces import DocLabel
from aymurai.meta.entities import CanonicalEntity

from aymurai.transforms.anonymization_postprocess.exact_labels import EXACT_LABELS


def _find_parent(parent: list[int], idx: int) -> int:
    """
    Finds the root representative of a union-find set with path compression.

    Args:
        parent (list[int]): Parent pointers for the union-find structure.
        idx (int): Index to resolve to its root.

    Returns:
        int: The root index for the provided `idx`.
    """
    if parent[idx] == idx:
        return idx
    parent[idx] = _find_parent(parent, parent[idx])
    return parent[idx]


def _union_parent(parent: list[int], left: int, right: int) -> None:
    """
    Unions two indices in a union-find structure.

    Args:
        parent (list[int]): Parent pointers for the union-find structure.
        left (int): First index to union.
        right (int): Second index to union.
    """
    root_left, root_right = _find_parent(parent, left), _find_parent(parent, right)
    if root_left != root_right:
        parent[root_right] = root_left


def _cluster_aliases_with_cdist(
    *,
    items: list[dict[str, str]],
    threshold: int,
) -> list[list[tuple[str, str, str]]]:
    """
    Clusters alias items using RapidFuzz pairwise similarity with union-find.

    Args:
        items (list[dict[str, str]]): Items containing "text" and "aymurai_label".
        threshold (int): Minimum similarity threshold for clustering.

    Returns:
        list[list[tuple[str, str, str]]]: Clusters of (original, normalized, label).
    """
    if not items:
        return []

    entities = [item.get("text", "") for item in items]
    labels = [item.get("aymurai_label", "UNKNOWN") for item in items]

    normed = [str(e).lower().strip() if e else "" for e in entities]

    sim = process.cdist(normed, normed, scorer=token_set_ratio, score_cutoff=threshold)

    parent = list(range(len(normed)))

    n = len(normed)
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i][j] >= threshold:
                _union_parent(parent, i, j)

    clusters_map: dict[int, list[tuple[str, str, str]]] = {}
    for idx in range(n):
        root = _find_parent(parent, idx)
        clusters_map.setdefault(root, []).append(
            (entities[idx], normed[idx], labels[idx])
        )

    return list(clusters_map.values())


def _parse_cluster_item(item: tuple[str, str, str]) -> tuple[str, str, str]:
    """
    Reorders a tuple from (original, normalized, label) to (label, original, normalized).

    Args:
        item (tuple[str, str, str]): Tuple in the form (original, normalized, label).

    Returns:
        tuple[str, str, str]: Tuple in the form (label, original, normalized).
    """
    orig, norm, label = item
    return label, orig, norm


def _pick_cluster_label(parsed_items: list[tuple[str, str, str]]) -> str:
    """
    Selects the most frequent label from a cluster.

    Args:
        parsed_items (list[tuple[str, str, str]]): Items in (label, original, normalized).

    Returns:
        str: The most common label in the cluster.
    """
    labels = [label for label, _, _ in parsed_items]
    return Counter(labels).most_common(1)[0][0]


def _pick_longest_alias(parsed_items: list[tuple[str, str, str]]) -> str:
    """
    Picks a canonical text representation from a cluster.

    Args:
        parsed_items (list[tuple[str, str, str]]): Items in (label, original, normalized).

    Returns:
        str: The longest alias text in the cluster.
    """
    return max(parsed_items, key=lambda item: len(item[1]))[1]


def _clusters_to_canonical_entities(
    clusters: list[list[tuple[str, str, str]]],
) -> list[CanonicalEntity]:
    """
    Converts clustered alias groups into CanonicalEntity objects.

    Args:
        clusters (list[list[tuple[str, str, str]]]): Clusters of
            (original, normalized, label).

    Returns:
        list[CanonicalEntity]: Canonical entities derived from clusters.
    """
    canonical_entities = []
    for cluster in clusters:
        parsed = [_parse_cluster_item(item) for item in cluster]
        label = _pick_cluster_label(parsed)
        canonical_text = _pick_longest_alias(parsed)
        aliases = sorted({orig for _, orig, _ in parsed})
        canonical_entities.append(
            CanonicalEntity(
                aymurai_label=label,
                canonical_text=canonical_text,
                aliases=aliases,
                attributes={},
            )
        )
    return canonical_entities


def build_canonical_entities(
    labels: Iterable[DocLabel],
    *,
    target_labels: set[str] | None = None,
    threshold: int,
) -> list[CanonicalEntity]:
    """
    Builds canonical entities by clustering label aliases per entity type.

    Args:
        labels (Iterable[DocLabel]): NER labels to cluster.
        target_labels (set[str] | None, optional): Label filter; if provided,
            only these labels are clustered. Defaults to None.
        threshold (int): Minimum similarity threshold for clustering.

    Returns:
        list[CanonicalEntity]: Canonical entities built from clustered aliases.
    """
    grouped: dict[str, list[dict[str, str]]] = {}
    for label in labels:
        attrs = label.attrs
        if not attrs or not attrs.aymurai_label:
            continue
        if target_labels and attrs.aymurai_label not in target_labels:
            continue
        alias = attrs.aymurai_alt_text or label.text

        subclass_val = getattr(attrs, "aymurai_label_subclass", None)

        if isinstance(subclass_val, list):
            exact_alias = subclass_val[-1] if subclass_val else alias
        else:
            exact_alias = subclass_val or alias

        grouped.setdefault(attrs.aymurai_label, []).append(
            {
                "text": alias,
                "aymurai_label": attrs.aymurai_label,
                "exact_alias": exact_alias,
            }
        )

    canonical_entities: list[CanonicalEntity] = []
    for label_type, items in grouped.items():
        if label_type in EXACT_LABELS:
            exact_groups = {}
            for item in items:
                exact_groups.setdefault(item["exact_alias"], []).append(item)
            clusters = [
                [
                    (
                        item["text"],
                        str(item["exact_alias"]).lower().strip(),
                        item["aymurai_label"],
                    )
                    for item in group_items
                ]
                for group_items in exact_groups.values()
            ]
        else:
            clusters = _cluster_aliases_with_cdist(
                items=items,
                threshold=threshold,
            )

        canonical_entities.extend(_clusters_to_canonical_entities(clusters))

    canonical_entities = sorted(canonical_entities, key=lambda x: x.canonical_text)

    return canonical_entities
