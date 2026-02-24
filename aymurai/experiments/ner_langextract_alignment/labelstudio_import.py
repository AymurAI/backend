from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_labelstudio_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return []


def _extract_manual_entities(
    annotation_result: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for item in annotation_result:
        if item.get("type") != "labels":
            continue
        value = item.get("value") or {}
        labels = value.get("labels") or []
        if not labels:
            continue
        entities.append(
            {
                "label": labels[0],
                "start_char": value.get("start"),
                "end_char": value.get("end"),
                "text": value.get("text", ""),
            }
        )
    return entities


def _extract_decision(annotation_result: list[dict[str, Any]]) -> str | None:
    valid = {"accept_ner", "accept_langextract", "edit_manual", "drop"}
    for item in annotation_result:
        if item.get("type") != "choices":
            continue
        value = item.get("value") or {}
        choices = value.get("choices") or []
        if not choices:
            continue
        choice = str(choices[0]).strip().lower()
        if choice in valid:
            return choice
    return None


def parse_labelstudio_decisions(
    tasks: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for task in tasks:
        meta = (task.get("data") or {}).get("meta_info") or {}
        sample_id = meta.get("sample_id")
        if not sample_id:
            continue

        annotations = task.get("annotations") or []
        if not annotations:
            continue

        annotation = annotations[0]
        result = annotation.get("result") or []
        decision = _extract_decision(result)
        manual_entities = _extract_manual_entities(result)

        if decision is None and manual_entities:
            decision = "edit_manual"

        decisions[str(sample_id)] = {
            "decision": decision,
            "manual_entities": manual_entities,
        }

    return decisions


def consolidate_datasets(
    samples: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train_candidates: list[dict[str, Any]] = []
    review_required: list[dict[str, Any]] = []

    for sample in samples:
        sample_id = str(sample.get("sample_id"))
        status = sample.get("comparison", {}).get("status")
        resolved = decisions.get(sample_id)

        if status == "match_full" and not resolved:
            sample["final_entities"] = sample.get("ner_predictions", [])
            sample["final_decision"] = "auto_match_full"
            train_candidates.append(sample)
            continue

        if not resolved:
            review_required.append(sample)
            continue

        decision = resolved.get("decision")
        if decision == "accept_ner":
            sample["final_entities"] = sample.get("ner_predictions", [])
            sample["final_decision"] = decision
            train_candidates.append(sample)
        elif decision == "accept_langextract":
            sample["final_entities"] = sample.get("langextract_predictions", [])
            sample["final_decision"] = decision
            train_candidates.append(sample)
        elif decision == "edit_manual":
            sample["final_entities"] = resolved.get("manual_entities", [])
            sample["final_decision"] = decision
            train_candidates.append(sample)
        elif decision == "drop":
            sample["final_entities"] = []
            sample["final_decision"] = decision
            review_required.append(sample)
        else:
            review_required.append(sample)

    return train_candidates, review_required
