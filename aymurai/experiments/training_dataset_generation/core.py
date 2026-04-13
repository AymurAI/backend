from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

try:
    from rapidfuzz import fuzz, process, utils

    def normalize_text_for_match(text: str) -> str:
        return utils.default_process(text)

    def extract_one_match(
        query: str,
        choices: list[str],
        *,
        score_cutoff: float,
    ) -> tuple[str, float, int] | None:
        return process.extractOne(
            query,
            choices,
            scorer=fuzz.ratio,
            score_cutoff=score_cutoff,
        )

except ModuleNotFoundError:

    def normalize_text_for_match(text: str) -> str:
        return re.sub(r"\s+", " ", str(text).strip().lower())

    def extract_one_match(
        query: str,
        choices: list[str],
        *,
        score_cutoff: float,
    ) -> tuple[str, float, int] | None:
        best: tuple[str, float, int] | None = None
        for index, choice in enumerate(choices):
            score = SequenceMatcher(None, query, choice).ratio() * 100
            if score < score_cutoff:
                continue
            if best is None or score > best[1]:
                best = (choice, score, index)
        return best


@dataclass(frozen=True)
class TrainSetStats:
    total_paragraphs: int
    labeled_count: int
    unlabeled_count: int
    label_document_frequency: dict[str, int]

    @property
    def background_ratio(self) -> float:
        if self.labeled_count == 0:
            return 0.0
        return self.unlabeled_count / self.labeled_count


def read_bio_lines(path: str | Path) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines()


def paragraphs_from_bio(path: str | Path) -> list[str]:
    paragraphs: list[str] = []
    current_tokens: list[str] = []

    for raw_line in read_bio_lines(path):
        line = raw_line.rstrip()
        if not line:
            if current_tokens:
                paragraphs.append(" ".join(current_tokens).strip())
                current_tokens = []
            continue

        try:
            token, _ = line.rsplit(" ", 1)
        except ValueError:
            token = line
        current_tokens.append(token)

    if current_tokens:
        paragraphs.append(" ".join(current_tokens).strip())

    return paragraphs


def parse_bio_paragraphs(path: str | Path) -> list[tuple[str, list[str]]]:
    paragraphs: list[tuple[str, list[str]]] = []
    current_tokens: list[str] = []
    current_labels: list[str] = []

    for raw_line in read_bio_lines(path):
        line = raw_line.rstrip()
        if not line:
            if current_tokens:
                paragraphs.append(
                    (" ".join(current_tokens).strip(), list(current_labels))
                )
                current_tokens = []
                current_labels = []
            continue

        try:
            token, label = line.rsplit(" ", 1)
        except ValueError:
            token = line
            label = ""

        current_tokens.append(token)
        current_labels.append(label.strip())

    if current_tokens:
        paragraphs.append((" ".join(current_tokens).strip(), list(current_labels)))

    return paragraphs


def normalize_bio_label(label: str) -> str:
    label = str(label).strip()
    if label.startswith("B-") or label.startswith("I-"):
        return label[2:]
    return label


def calculate_train_set_stats(
    parsed_paragraphs: list[tuple[str, list[str]]]
) -> TrainSetStats:
    labeled_count = 0
    unlabeled_count = 0
    label_document_frequency: dict[str, int] = {}

    for _, labels in parsed_paragraphs:
        normalized_labels = {
            normalize_bio_label(label) for label in labels if label and label != "O"
        }
        if normalized_labels:
            labeled_count += 1
            for label in normalized_labels:
                label_document_frequency[label] = (
                    label_document_frequency.get(label, 0) + 1
                )
        else:
            unlabeled_count += 1

    return TrainSetStats(
        total_paragraphs=len(parsed_paragraphs),
        labeled_count=labeled_count,
        unlabeled_count=unlabeled_count,
        label_document_frequency=dict(
            sorted(
                label_document_frequency.items(), key=lambda item: (item[1], item[0])
            )
        ),
    )


def load_new_candidates(jsonl_path: str | Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    with Path(jsonl_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            candidates.append(
                {
                    "text": data.get("text", ""),
                    "entities": data.get("final_entities", [])
                    or data.get("entities", []),
                }
            )
    return candidates


def perform_internal_deduplication(
    candidates: list[dict[str, Any]],
    threshold: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unique_candidates: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    processed_texts: list[str] = []

    for candidate in candidates:
        raw_text = str(candidate.get("text", "")).strip()
        if not raw_text:
            continue
        processed_text = normalize_text_for_match(raw_text)
        match = extract_one_match(
            processed_text,
            processed_texts,
            score_cutoff=threshold,
        )
        if match:
            _, score, index = match
            duplicated = dict(candidate)
            duplicated["internal_similarity_score"] = score
            duplicated["duplicate_of"] = unique_candidates[index]["text"]
            duplicates.append(duplicated)
            continue

        unique_candidates.append(candidate)
        processed_texts.append(processed_text)

    return unique_candidates, duplicates


def is_noise(text: str) -> bool:
    return re.search(r"[a-zA-Z0-9]", text) is None


def perform_corpus_deduplication(
    new_candidates: list[dict[str, Any]],
    existing_corpus: Iterable[str],
    threshold: float,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    clean_labeled: list[dict[str, Any]] = []
    clean_unlabeled: list[dict[str, Any]] = []
    duplicates_with_labels: list[dict[str, Any]] = []
    duplicates_without_labels: list[dict[str, Any]] = []
    discarded_noise: list[dict[str, Any]] = []

    corpus_as_list = list(existing_corpus)
    normalized_corpus = [normalize_text_for_match(text) for text in corpus_as_list]

    for candidate in new_candidates:
        raw_text = str(candidate.get("text", "")).strip()
        if not raw_text or is_noise(raw_text):
            discarded = dict(candidate)
            discarded["reason"] = "noise"
            discarded_noise.append(discarded)
            continue

        processed_text = normalize_text_for_match(raw_text)
        current_threshold = 100 if len(raw_text) < 15 else threshold
        entities = candidate.get("entities", []) or []
        has_labels = bool(entities)

        match = extract_one_match(
            processed_text,
            normalized_corpus,
            score_cutoff=current_threshold,
        )
        if match:
            _, score, index = match
            duplicated = dict(candidate)
            duplicated["similarity_score"] = score
            duplicated["matched_with"] = corpus_as_list[index]
            duplicated["reason"] = (
                "duplicate_with_labels" if has_labels else "duplicate_without_labels"
            )
            if has_labels:
                duplicates_with_labels.append(duplicated)
            else:
                duplicates_without_labels.append(duplicated)
            continue

        if has_labels:
            clean_labeled.append(candidate)
        else:
            clean_unlabeled.append(candidate)

    return (
        clean_labeled,
        clean_unlabeled,
        duplicates_with_labels,
        duplicates_without_labels,
        discarded_noise,
    )


def load_target_labels_from_txt(path: str | Path) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    if not cleaned_lines:
        return []

    header = cleaned_lines[0].split("\t")
    if "label" in [column.strip() for column in header]:
        labels: list[str] = []
        for line in cleaned_lines[1:]:
            parts = [item.strip() for item in line.split("\t")]
            if not parts or not parts[0]:
                continue
            labels.append(parts[0])
        return labels

    return cleaned_lines


def resolve_target_labels(
    *,
    original_train_stats: TrainSetStats,
    low_frequency_labels_path: str | None,
    low_frequency_top_k: int,
) -> list[str]:
    if low_frequency_labels_path:
        labels = load_target_labels_from_txt(low_frequency_labels_path)
        return labels[:low_frequency_top_k]
    return list(original_train_stats.label_document_frequency.keys())[
        :low_frequency_top_k
    ]


def extract_candidate_labels(candidate: dict[str, Any]) -> set[str]:
    return {
        str(entity.get("label", "")).strip()
        for entity in candidate.get("entities", []) or []
        if str(entity.get("label", "")).strip()
    }


def filter_labeled_candidates(
    candidates: list[dict[str, Any]],
    *,
    mode: str,
    target_labels: set[str],
    min_target_labels_per_candidate: int,
) -> list[dict[str, Any]]:
    if mode == "all_clean_labeled":
        return list(candidates)

    filtered: list[dict[str, Any]] = []
    for candidate in candidates:
        labels = extract_candidate_labels(candidate)
        matched_target_labels = sorted(labels & target_labels)
        if len(matched_target_labels) < min_target_labels_per_candidate:
            continue
        enriched = dict(candidate)
        enriched["matched_target_labels"] = matched_target_labels
        filtered.append(enriched)
    return filtered


def sample_unlabeled_candidates(
    clean_unlabeled: list[dict[str, Any]],
    *,
    selected_labeled_count: int,
    original_train_stats: TrainSetStats,
    include_original_train: bool,
    mode: str,
    target_background_to_labeled_ratio: float,
    fixed_count: int | None,
    seed: int,
) -> list[dict[str, Any]]:
    if mode == "none":
        return []

    base_labeled = original_train_stats.labeled_count if include_original_train else 0
    base_unlabeled = (
        original_train_stats.unlabeled_count if include_original_train else 0
    )

    if mode == "ratio_to_selected_labeled":
        desired_count = math.ceil(
            selected_labeled_count * target_background_to_labeled_ratio
        )
    elif mode == "target_total_background_ratio":
        desired_total_unlabeled = math.ceil(
            (base_labeled + selected_labeled_count) * target_background_to_labeled_ratio
        )
        desired_count = max(0, desired_total_unlabeled - base_unlabeled)
    elif mode == "preserve_original_background_ratio":
        desired_total_unlabeled = math.ceil(
            (base_labeled + selected_labeled_count)
            * original_train_stats.background_ratio
        )
        desired_count = max(0, desired_total_unlabeled - base_unlabeled)
    elif mode == "fixed_count":
        desired_count = fixed_count or 0
    else:
        raise ValueError(f"Unsupported unlabeled sampling mode: {mode}")

    if desired_count <= 0:
        return []

    rng = random.Random(seed)
    sample_size = min(desired_count, len(clean_unlabeled))
    return rng.sample(clean_unlabeled, sample_size)


def shuffle_candidates(
    candidates: list[dict[str, Any]], *, seed: int
) -> list[dict[str, Any]]:
    shuffled = list(candidates)
    random.Random(seed).shuffle(shuffled)
    return shuffled


def export_jsonl(records: list[dict[str, Any]], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_token_offsets(text: str, tokens: list[str]) -> list[tuple[int, int]]:
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for token in tokens:
        start = text.find(token, cursor)
        if start == -1:
            raise ValueError(
                f"Could not align token '{token}' around '{text[cursor : cursor + 80]}'"
            )
        end = start + len(token)
        offsets.append((start, end))
        cursor = end
    return offsets


def convert_json_to_bio(entry: dict[str, Any]) -> list[str]:
    text = str(entry.get("text", ""))
    entities = sorted(
        entry.get("entities", []) or [],
        key=lambda item: (item["start_char"], item["end_char"]),
    )
    tokens = text.split()
    offsets = build_token_offsets(text, tokens)
    bio_tags = ["O"] * len(tokens)

    for entity in entities:
        first = True
        for idx, (tok_start, tok_end) in enumerate(offsets):
            if entity["end_char"] <= tok_start or entity["start_char"] >= tok_end:
                continue
            prefix = "B-" if first else "I-"
            bio_tags[idx] = f"{prefix}{entity['label']}"
            first = False

    return [f"{token} {label}" for token, label in zip(tokens, bio_tags)]


def write_bio_dataset(
    *,
    original_train_path: str | Path,
    selected_candidates: list[dict[str, Any]],
    output_path: str | Path,
    include_original_train: bool,
) -> dict[str, int]:
    output_lines: list[str] = []
    appended_candidates = 0
    skipped_candidates = 0

    if include_original_train:
        original_text = Path(original_train_path).read_text(encoding="utf-8")
        output_lines.append(original_text)
        if original_text and not original_text.endswith("\n\n"):
            output_lines.append("\n")

    for candidate in selected_candidates:
        try:
            bio_lines = convert_json_to_bio(candidate)
        except ValueError:
            skipped_candidates += 1
            continue

        if not bio_lines:
            skipped_candidates += 1
            continue

        output_lines.extend(f"{line}\n" for line in bio_lines)
        output_lines.append("\n")
        appended_candidates += 1

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("".join(output_lines), encoding="utf-8")

    return {
        "appended_candidates": appended_candidates,
        "skipped_candidates": skipped_candidates,
    }
