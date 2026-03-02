from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from aymurai.logger import get_logger
from aymurai.utils.json_data import load_json

logger = get_logger(__name__)


def normalize_text(text: str) -> str:
    """
    Normalize text by lowercasing, stripping, and removing accents.

    Args:
        text (str): Input text.

    Returns:
        str: Normalized text.
    """
    if not text:
        return ""

    # Lowercase and strip
    text = text.strip().lower()

    # Remove accents
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    return text


def get_alias_set(entity: dict[str, Any], normalize: bool = True) -> set[str]:
    """
    Returns the set of normalized aliases for an entity, ensuring that the
    canonical_text is included as an alias.

    Args:
        entity (dict[str, Any]): A dictionary containing entity information with
            optional 'aliases' (list of strings) and 'canonical_text' (string) keys.
        normalize (bool, optional): If True, normalizes the alias texts using
            normalize_text function. Defaults to True.

    Returns:
        set[str]: A set of alias strings (normalized if normalize=True) including
            both explicit aliases and the canonical text.
    """
    aliases = set()

    # Get aliases from the entity
    for alias in entity.get("aliases", []):
        text = normalize_text(alias) if normalize else alias
        if text:
            aliases.add(text)

    # Get canonical text from the entity
    canonical = (
        normalize_text(entity.get("canonical_text", ""))
        if normalize
        else entity.get("canonical_text", "")
    )
    if canonical:
        aliases.add(canonical)

    return aliases


def alias_jaccard(aliases_gold: set[str], aliases_pred: set[str]) -> float:
    """
    Jaccard similarity between two sets of aliases.

    Args:
        aliases_gold (set[str]): Set of gold aliases.
        aliases_pred (set[str]): Set of predicted aliases.

    Returns:
        float: Jaccard similarity score.
    """
    # If both sets are empty, define similarity as 1.0
    if not aliases_gold and not aliases_pred:
        return 1.0

    # Calculate Jaccard similarity
    union = aliases_gold | aliases_pred
    inter = aliases_gold & aliases_pred

    return len(inter) / len(union)


def greedy_matching(
    sim_matrix: list[list[float]], sim_threshold: float
) -> list[tuple[int, int, float]]:
    """
    Perform greedy maximum matching based on similarity scores.

    Args:
        sim_matrix (list[list[float]]): Similarity matrix where sim_matrix[i][j]
            represents the similarity between the gold entity i and predicted
            entity j.
        sim_threshold (float): Minimum similarity required to consider a match
            between two entities.

    Returns:
        list[tuple[int, int, float]]: Tuples containing the matched gold index,
            predicted index, and their similarity score.
    """
    matches: list[tuple[int, int, float]] = []
    num_gold = len(sim_matrix)
    num_pred = len(sim_matrix[0]) if num_gold > 0 else 0

    # Build the list of candidate matches above the threshold
    candidates: list[tuple[float, int, int]] = []
    for i in range(num_gold):
        for j in range(num_pred):
            sim = sim_matrix[i][j]
            if sim >= sim_threshold:
                candidates.append((sim, i, j))

    # Sort descending by similarity so higher matches are selected first
    candidates.sort(reverse=True, key=lambda x: x[0])

    used_gold = set()
    used_pred = set()

    for sim, i, j in candidates:
        if i in used_gold or j in used_pred:
            continue
        used_gold.add(i)
        used_pred.add(j)
        matches.append((i, j, sim))

    return matches


def compute_metrics_components(
    gold_entities: list[dict[str, Any]],
    pred_entities: list[dict[str, Any]],
    sim_threshold: float = 0.3,
    normalize: bool = True,
    target_label: str = None,
) -> dict[str, float]:
    """
    Compute each component of the disambiguation metric by label if provided.

    The metric includes entity-level F1, macro average alias F1, and accuracy
    for labels and roles on matched entities.

    Args:
        gold_entities (list[dict[str, Any]]): Ground-truth entities.
        pred_entities (list[dict[str, Any]]): Predicted entities.
        sim_threshold (float): Minimum alias similarity to consider entities a match.
            Defaults to 0.3.
        normalize (bool): If True normalizes aliases before comparison.
            Defaults to True.

    Returns:
        dict[str, float]: Mapping with the keys F1_ent, AliasF1_macro, Acc_label, and Acc_role.
    """
    # Filter entities by target label if provided
    if target_label:
        gold_entities = [
            e for e in gold_entities if e.get("aymurai_label") == target_label
        ]
        pred_entities = [
            e for e in pred_entities if e.get("aymurai_label") == target_label
        ]

    # Handle the trivial case where both sets are empty
    if not gold_entities and not pred_entities:
        return {
            "F1_ent": 1.0,
            "AliasF1_macro": 1.0,
            "Acc_label": 1.0,
            "Acc_role": 1.0,
        }

    # Preprocess aliases, labels and roles
    gold_aliases = [get_alias_set(e, normalize=normalize) for e in gold_entities]
    pred_aliases = [get_alias_set(e, normalize=normalize) for e in pred_entities]

    gold_labels = [e.get("aymurai_label") for e in gold_entities]
    pred_labels = [e.get("aymurai_label") for e in pred_entities]

    gold_roles = [e.get("attributes", {}).get("role") for e in gold_entities]
    pred_roles = [e.get("attributes", {}).get("role") for e in pred_entities]

    num_gold = len(gold_entities)
    num_pred = len(pred_entities)

    # Build the alias similarity matrix
    sim_matrix = []
    for i in range(num_gold):
        row = []
        for j in range(num_pred):
            sim = alias_jaccard(gold_aliases[i], pred_aliases[j])
            row.append(sim)
        sim_matrix.append(row)

    # Perform greedy matching
    matches = greedy_matching(sim_matrix, sim_threshold=sim_threshold)

    TP = len(matches)
    FN = num_gold - TP
    FP = num_pred - TP

    # Entity-level precision/recall/F1
    if TP + FP > 0:
        P_ent = TP / (TP + FP)
    else:
        P_ent = 0.0

    if TP + FN > 0:
        R_ent = TP / (TP + FN)
    else:
        R_ent = 0.0

    if P_ent + R_ent > 0:
        F1_ent = 2 * P_ent * R_ent / (P_ent + R_ent)
    else:
        F1_ent = 0.0

    # Alias-level F1 macro
    if TP > 0:
        alias_f1_sum = 0.0
        label_correct = 0
        role_correct = 0

        for i, j, _sim in matches:
            A_g = gold_aliases[i]
            A_p = pred_aliases[j]

            inter = len(A_g & A_p)
            P_alias = inter / len(A_p) if len(A_p) > 0 else 0.0
            R_alias = inter / len(A_g) if len(A_g) > 0 else 0.0
            if P_alias + R_alias > 0:
                F1_alias = 2 * P_alias * R_alias / (P_alias + R_alias)
            else:
                F1_alias = 0.0

            alias_f1_sum += F1_alias

            # Label accuracy on matched entities
            if gold_labels[i] == pred_labels[j]:
                label_correct += 1

            # Role accuracy on matched entities
            if gold_roles[i] == pred_roles[j]:
                role_correct += 1

        AliasF1_macro = alias_f1_sum / TP
        Acc_label = label_correct / TP
        Acc_role = role_correct / TP
    else:
        AliasF1_macro = 0.0
        Acc_label = 0.0
        Acc_role = 0.0

    return {
        "F1_ent": F1_ent,
        "AliasF1_macro": AliasF1_macro,
        "Acc_label": Acc_label,
        "Acc_role": Acc_role,
    }


def evaluate_disambiguation(
    gold_json: Any,
    pred_json: Any,
    w_ent: float = 0.4,
    w_alias: float = 0.35,
    w_label: float = 0.2,
    w_role: float = 0.05,
    sim_threshold: float = 0.3,
    normalize: bool = True,
    target_label: str = None,
) -> tuple[float, dict[str, float]]:
    """
    Evaluate disambiguation predictions against ground truth entities by label if provided.

    Args:
        gold_json (Any): Ground-truth entities as a parsed list or JSON string.
        pred_json (Any): Predicted entities as a parsed list or JSON string.
        w_ent (float): Weight assigned to entity-level F1. Defaults to 0.4.
        w_alias (float): Weight assigned to alias macro F1. Defaults to 0.35.
        w_label (float): Weight assigned to label accuracy. Defaults to 0.2.
        w_role (float): Weight assigned to role accuracy. Defaults to 0.05.
        sim_threshold (float): Minimum alias similarity to consider entities a match.
            Defaults to 0.3.
        normalize (bool): If True normalizes aliases before comparison.
            Defaults to True.

    Returns:
        tuple[float, dict[str, float]]: Overall disambiguation score and detailed metrics components.
    """

    # Parse JSON strings if necessary
    if isinstance(gold_json, str):
        gold_entities = json.loads(gold_json)
    else:
        gold_entities = gold_json

    if isinstance(pred_json, str):
        pred_entities = json.loads(pred_json)
    else:
        pred_entities = pred_json

    metrics = compute_metrics_components(
        gold_entities,
        pred_entities,
        sim_threshold=sim_threshold,
        normalize=normalize,
        target_label=target_label,
    )

    score = (
        w_ent * metrics["F1_ent"]
        + w_alias * metrics["AliasF1_macro"]
        + w_label * metrics["Acc_label"]
        + w_role * metrics["Acc_role"]
    )

    return score, metrics


def evaluate_prediction_directories(
    gold_dir: Path,
    preds_dir: Path,
    *,
    sim_threshold: float = 0.3,
    normalize: bool = True,
    target_label: str = None,
    gold_json_suffix: str = None,
    pred_json_suffix: str = None,
) -> tuple[list[tuple[str, float, dict[str, float]]], float]:
    """
    Evaluate predictions stored on disk against the gold standard set by label if provided.
    It has the feature of comparing files in two directories based on their core names,
    ignoring predefined suffixes.

    Args:
        gold_dir (Path): Directory containing gold json files.
        preds_dir (Path): Directory containing predicted json files.
        sim_threshold (float): Minimum alias similarity to consider entities a match.
            Defaults to 0.3.
        normalize (bool): If True normalizes aliases before comparison.
            Defaults to True.
        target_label (str, optional): If provided, evaluates only entities with this label.
            Defaults to None.
        gold_json_suffix (str, optional): Suffix to remove from gold json filenames
            when matching with predictions. Defaults to None.
        pred_json_suffix (str, optional): Suffix to remove from predicted json filenames
            when matching with gold files. Defaults to None.

    Returns:
        tuple[list[tuple[str, float, dict[str, float]]], float]: Detailed results
        per document and the average score across all evaluated documents.
    """
    gold_dir = Path(gold_dir)
    preds_dir = Path(preds_dir)

    results = []

    pred_map = {}
    for p in preds_dir.glob("*.json"):
        core_name = p.stem.replace(pred_json_suffix, "")
        pred_map[core_name] = p

    for gold_path in sorted(gold_dir.glob("*.json")):
        core_id = gold_path.stem.replace(gold_json_suffix, "")
        pred_path = pred_map.get(core_id)

        if not pred_path or not pred_path.exists():
            logger.warning(
                f"Skipping: No prediction found for '{core_id}'. "
                f"Expected something like '{core_id}{pred_json_suffix}.json'"
            )
            continue

        gold_data = load_json(gold_path)
        pred_data = load_json(pred_path)

        score, metrics = evaluate_disambiguation(
            gold_data,
            pred_data,
            sim_threshold=sim_threshold,
            normalize=normalize,
            target_label=target_label,
        )
        results.append((core_id, score, metrics))

    average_score = (
        sum(score for _, score, _ in results) / len(results)
        if results
        else float("nan")
    )

    return results, average_score
