from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Métrica para Desambiguación


def normalize_text(text: str) -> str:
    """
    Normaliza un alias:
    - pasa a minúsculas
    - elimina espacios extra
    - quita tildes/acentos
    """
    if text is None:
        return ""
    text = text.strip().lower()
    # eliminar acentos
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def get_alias_set(entity: Dict[str, Any], normalize: bool = True) -> Set[str]:
    """
    Devuelve el conjunto de aliases normalizados para una entidad,
    asegurándose de incluir el canonical_text como alias.
    """
    aliases = set()
    # aliases explícitos
    for alias in entity.get("aliases", []):
        text = normalize_text(alias) if normalize else alias
        if text:
            aliases.add(text)
    canonical = (
        normalize_text(entity.get("canonical_text", ""))
        if normalize
        else entity.get("canonical_text", "")
    )
    if canonical:
        aliases.add(canonical)

    return aliases


def alias_jaccard(aliases_gold: Set[str], aliases_pred: Set[str]) -> float:
    """
    Similaridad Jaccard entre conjuntos de aliases.
    """
    if not aliases_gold and not aliases_pred:
        return 1.0
    union = aliases_gold | aliases_pred
    if not union:
        return 0.0
    inter = aliases_gold & aliases_pred
    return len(inter) / len(union)


def greedy_matching(
    sim_matrix: List[List[float]], sim_threshold: float
) -> List[Tuple[int, int, float]]:
    """
    Emparejamiento greedy máximo por similitud:
    - sim_matrix[i][j] = similitud entre entidad gold i y pred j
    - sim_threshold: mínimo para considerar un match

    Devuelve una lista de tuplas (i_gold, j_pred, sim).
    """
    matches: List[Tuple[int, int, float]] = []
    num_gold = len(sim_matrix)
    num_pred = len(sim_matrix[0]) if num_gold > 0 else 0

    # Generar la lista de candidatos (i, j, sim) por encima del umbral
    candidates: List[Tuple[float, int, int]] = []
    for i in range(num_gold):
        for j in range(num_pred):
            sim = sim_matrix[i][j]
            if sim >= sim_threshold:
                candidates.append((sim, i, j))

    # Ordenar descendente por similitud
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
    gold_entities: List[Dict[str, Any]],
    pred_entities: List[Dict[str, Any]],
    sim_threshold: float = 0.3,
    normalize: bool = True,
) -> Dict[str, float]:
    """
    Calcula los componentes de la métrica:
    - F1_ent: F1 de entidades (detección de entidades canónicas)
    - AliasF1_macro: F1 macro promedio sobre aliases por entidad emparejada
    - Acc_label: accuracy de labels en entidades emparejadas
    - Acc_role: accuracy de roles en entidades emparejadas
    """

    # Caso trivial: sin entidades en ambos
    if not gold_entities and not pred_entities:
        return {
            "F1_ent": 1.0,
            "AliasF1_macro": 1.0,
            "Acc_label": 1.0,
            "Acc_role": 1.0,
        }

    # Preprocesar aliases, labels y roles
    gold_aliases = [get_alias_set(e, normalize=normalize) for e in gold_entities]
    pred_aliases = [get_alias_set(e, normalize=normalize) for e in pred_entities]

    gold_labels = [e.get("aymurai_label") for e in gold_entities]
    pred_labels = [e.get("aymurai_label") for e in pred_entities]

    gold_roles = [e.get("attributes", {}).get("role") for e in gold_entities]
    pred_roles = [e.get("attributes", {}).get("role") for e in pred_entities]

    num_gold = len(gold_entities)
    num_pred = len(pred_entities)

    # Matriz de similitud de aliases
    sim_matrix: List[List[float]] = []
    for i in range(num_gold):
        row = []
        for j in range(num_pred):
            sim = alias_jaccard(gold_aliases[i], pred_aliases[j])
            row.append(sim)
        sim_matrix.append(row)

    # Matching greedy
    matches = greedy_matching(sim_matrix, sim_threshold=sim_threshold)

    TP = len(matches)
    FN = num_gold - TP
    FP = num_pred - TP

    # Entidad-level precision/recall/F1
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

            # label
            if gold_labels[i] == pred_labels[j]:
                label_correct += 1

            # rol
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
) -> Tuple[float, Dict[str, float]]:
    """
    Función principal de evaluación:
    - gold_json: JSON ground truth (lista de entidades o string JSON)
    - pred_json: JSON predicho (lista de entidades o string JSON)
    - w_ent, w_alias, w_label, w_role: pesos de cada componente
    - sim_threshold: umbral mínimo de similitud de aliases para emparejar entidades

    Devuelve una tupla (Score_global, métricas_componentes) donde:
    - Score_global es un escalar entre 0 y 1.
    - métricas_componentes es un dict con los valores individuales de cada métrica.
    """

    # Si vienen como string, parsear JSON
    if isinstance(gold_json, str):
        gold_entities = json.loads(gold_json)
    else:
        gold_entities = gold_json

    if isinstance(pred_json, str):
        pred_entities = json.loads(pred_json)
    else:
        pred_entities = pred_json

    metrics = compute_metrics_components(
        gold_entities, pred_entities, sim_threshold=sim_threshold, normalize=normalize
    )

    score = (
        w_ent * metrics["F1_ent"]
        + w_alias * metrics["AliasF1_macro"]
        + w_label * metrics["Acc_label"]
        + w_role * metrics["Acc_role"]
    )

    return score, metrics


def evaluate_prediction_directories(
    test_dir: Path,
    preds_dir: Path,
    *,
    sim_threshold: float = 0.3,
    normalize: bool = True,
) -> Tuple[List[Tuple[str, float, Dict[str, float]]], float]:
    """Evalúa predicciones contra el set gold utilizando la métrica de desambiguación.

    Devuelve una lista con tuplas (documento, score, métricas) y el score promedio.
    """
    test_dir = Path(test_dir)
    preds_dir = Path(preds_dir)

    results: List[Tuple[str, float, Dict[str, float]]] = []

    for test_path in sorted(test_dir.glob("*_test.json")):
        prefix = test_path.name[: -len("_test.json")]
        pred_path = preds_dir / f"{prefix}_pred.json"

        if not pred_path.exists():
            print(f"[WARN] No se encontró predicción para {test_path.name}; se omite.")
            continue

        with test_path.open(encoding="utf-8") as fh:
            gold_data = json.load(fh)
        with pred_path.open(encoding="utf-8") as fh:
            pred_data = json.load(fh)

        score, metrics = evaluate_disambiguation(
            gold_data,
            pred_data,
            sim_threshold=sim_threshold,
            normalize=normalize,
        )
        results.append((prefix, score, metrics))

    average_score = (
        sum(score for _, score, _ in results) / len(results)
        if results
        else float("nan")
    )
    return results, average_score
