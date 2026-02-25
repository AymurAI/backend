from __future__ import annotations

import json
import random
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any


def _make_region(
    *,
    start: int,
    end: int,
    text: str,
    label: str,
    from_name: str,
    to_name: str,
    diff_tag: str,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex[:10],
        "from_name": from_name,
        "to_name": to_name,
        "type": "labels",
        "value": {
            "start": start,
            "end": end,
            "text": text,
            "labels": [label],
        },
        "meta": {"diff_tag": diff_tag},
    }


def _prediction_payload(
    *,
    entities: list[dict[str, Any]],
    model_version: str,
    from_name: str,
    to_name: str,
    diff_tag: str,
) -> dict[str, Any]:
    results = [
        _make_region(
            start=ent["start_char"],
            end=ent["end_char"],
            text=ent["text"],
            label=ent["label"],
            from_name=from_name,
            to_name=to_name,
            diff_tag=diff_tag,
        )
        for ent in entities
    ]
    return {
        "model_version": model_version,
        "result": results,
    }


def sample_agreements_stratified(
    match_samples: list[dict[str, Any]],
    qa_rate: float,
    seed: int,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in match_samples:
        labels = {
            entity.get("label")
            for entity in sample.get("comparison", {}).get("exact_match", [])
            if entity.get("label")
        }
        group_key = "|".join(sorted(labels)) if labels else "__NO_ENTITY__"
        groups[group_key].append(sample)

    rng = random.Random(seed)
    out: list[dict[str, Any]] = []

    for _, items in sorted(groups.items(), key=lambda x: x[0]):
        if not items:
            continue
        rng.shuffle(items)
        if qa_rate <= 0:
            continue
        k = max(1, int(len(items) * qa_rate))
        out.extend(items[:k])

    return out


def build_task(sample: dict[str, Any]) -> dict[str, Any]:
    status = sample.get("comparison", {}).get("status", "mixed")
    task = {
        "data": {
            "text": sample.get("text", ""),
            "meta_info": {
                "sample_id": sample.get("sample_id"),
                "document_id": sample.get("document_id"),
                "paragraph_id": sample.get("paragraph_id"),
                "source_path": sample.get("source_path"),
                "status": status,
            },
        },
        "predictions": [
            _prediction_payload(
                entities=sample.get("ner_predictions", []),
                model_version="ner_api",
                from_name="label",
                to_name="text",
                diff_tag="only_ner",
            ),
            _prediction_payload(
                entities=sample.get("langextract_predictions", []),
                model_version="langextract",
                from_name="label",
                to_name="text",
                diff_tag="only_langextract",
            ),
            _prediction_payload(
                entities=sample.get("comparison", {}).get("exact_match", []),
                model_version="exact_match",
                from_name="label",
                to_name="text",
                diff_tag="exact_match",
            ),
            _prediction_payload(
                entities=sample.get("comparison", {}).get("partial_match", []),
                model_version="partial_match",
                from_name="label",
                to_name="text",
                diff_tag="partial_match",
            ),
        ],
    }
    return task


def export_labelstudio_tasks(
    *,
    samples: list[dict[str, Any]],
    export_dir: Path,
    qa_sample_rate: float,
    qa_seed: int,
) -> dict[str, Path]:
    export_dir.mkdir(parents=True, exist_ok=True)

    discrepancies = [
        s
        for s in samples
        if s.get("comparison", {}).get("status")
        in {"ner_only", "langextract_only", "mixed"}
    ]
    agreements = [
        s for s in samples if s.get("comparison", {}).get("status") == "exact_match"
    ]
    sampled_agreements = sample_agreements_stratified(
        agreements, qa_sample_rate, qa_seed
    )
    partial_agreements = [
        s for s in samples if s.get("comparison", {}).get("status") == "partial_match"
    ]

    discrepancies_tasks = [build_task(s) for s in discrepancies]
    agreements_tasks = [build_task(s) for s in sampled_agreements]
    partial_agreements_tasks = [build_task(s) for s in partial_agreements]

    discrepancies_path = export_dir / "discrepancies.json"
    agreements_path = export_dir / "agreements_qa_sample.json"
    partial_agreements_path = export_dir / "partial_agreements.json"

    discrepancies_path.write_text(
        json.dumps(discrepancies_tasks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    agreements_path.write_text(
        json.dumps(agreements_tasks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    partial_agreements_path.write_text(
        json.dumps(partial_agreements_tasks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "discrepancies": discrepancies_path,
        "agreements_qa_sample": agreements_path,
        "partial_agreements": partial_agreements_path,
    }
