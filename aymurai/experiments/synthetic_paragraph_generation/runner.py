from __future__ import annotations

import argparse
import json
import random
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel
import re
from tqdm.auto import tqdm

from aymurai.experiments.data_augmentation.runner import (
    entities_to_bio_lines,
    generate_label_candidates,
    load_augmentation_registry,
)
from aymurai.experiments.training_dataset_generation.core import (
    extract_one_match,
    normalize_text_for_match,
    parse_bio_paragraphs,
    paragraphs_from_bio,
)
from aymurai.experiments.synthetic_paragraph_generation.config import (
    SyntheticParagraphGenerationConfig,
    load_synthetic_paragraph_generation_config,
    render_run_dir_name,
)


class SyntheticEntityResponse(BaseModel):
    label: str
    value: str


class SyntheticParagraphResponse(BaseModel):
    job_id: str
    paragraph: str
    entities: list[SyntheticEntityResponse]


class SyntheticParagraphBatchResponse(BaseModel):
    paragraphs: list[SyntheticParagraphResponse]


@dataclass(frozen=True)
class ExampleRecord:
    sample_id: str
    text: str
    labels: list[str]


@dataclass(frozen=True)
class PromptBatch:
    labels: list[str]
    prompt: str
    prompt_token_count: int
    paragraph_jobs: list[dict[str, Any]]
    missing_labels: list[str]
    reference_examples: dict[str, list[ExampleRecord]]
    reduced_examples_per_label: dict[str, int]


LLM_SYSTEM_PROMPT = """You generate synthetic Spanish legal paragraphs for NER training.
Write new paragraphs inspired by the examples and guidelines.
Use the provided entity values exactly as given.
Do not wrap entity values in tags.
Return only the JSON object required by the schema.
"""


LLM_USER_PROMPT_TEMPLATE = """
Generate synthetic Spanish legal paragraphs.

Guidelines:
{guidelines}

Reference examples by target label:
{examples_block}

Requested labels for these paragraphs:
{labels_json}

Paragraph jobs with exact entity values you must use verbatim:
{paragraph_jobs_json}

Labels that you may invent because Faker does not provide them:
{llm_only_labels_json}

Rules:
- Create exactly {paragraphs_per_call} paragraphs, one per paragraph job.
- Keep the style close to real judicial or prosecutorial text from Argentina.
- Do not write the label tags in the paragraph, only the values.
- For each paragraph job, include every provided entity value exactly once in that paragraph.
- For each LLM-only label, invent one realistic value and include it exactly once.
- Do not use angle brackets or placeholder tags.
- Do not explain your choices.
- Return JSON with:
  - paragraphs: a list with exactly {paragraphs_per_call} items
  - each item must contain:
    - job_id
    - paragraph
    - entities
""".strip()


def log_step(message: str) -> None:
    print(f"[synthetic-paragraph-generation] {message}")


def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def iter_jsonl_rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSONL at {path}:{line_number}: {exc}"
                ) from exc


def normalize_bio_labels(tags: list[str]) -> list[str]:
    clean = set()
    for tag in tags:
        if not tag or tag == "O":
            continue
        parts = tag.split("-", 1)
        clean.add(parts[-1])
    return sorted(list(clean))


def strip_label_names_from_text(text: str, labels: list[str]) -> str:
    if not labels:
        return text
    sorted_labels = sorted(labels, key=len, reverse=True)
    pattern = r"\b(" + "|".join(re.escape(label) for label in sorted_labels) + r")\b"

    clean_text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", clean_text).strip()


def parse_example_row(
    row: dict[str, Any],
    *,
    index: int,
    text_field: str,
    labels_field: str,
) -> ExampleRecord | None:
    text = str(
        row.get(text_field)
        or row.get("text")
        or row.get("resolved_text")
        or row.get("source_text")
        or ""
    ).strip()
    if not text:
        return None

    raw_labels = row.get(labels_field)
    if isinstance(raw_labels, list):
        normalized_raw_labels: list[str] = []
        for item in raw_labels:
            if isinstance(item, dict) and item.get("label"):
                normalized_raw_labels.append(str(item["label"]))
            elif isinstance(item, str):
                normalized_raw_labels.append(item)
        raw_labels = normalized_raw_labels
    else:
        raw_labels = []
        for entity_key in (
            "entities",
            "final_entities",
            "ner_predictions",
            "langextract_predictions",
        ):
            entities = row.get(entity_key) or []
            raw_labels.extend(
                entity.get("label") for entity in entities if entity.get("label")
            )

        comparison = row.get("comparison") or {}
        for comparison_key in (
            "exact_match",
            "partial_match",
            "only_in_ner",
            "only_in_langextract",
        ):
            entities = comparison.get(comparison_key) or []
            raw_labels.extend(
                entity.get("label") for entity in entities if entity.get("label")
            )

    labels = sorted({str(label).strip() for label in raw_labels if str(label).strip()})
    if not labels:
        return None

    return ExampleRecord(
        sample_id=str(row.get("sample_id") or f"example-{index}"),
        text=text,
        labels=labels,
    )


def ensure_exact_examples_per_label(
    label_to_examples: dict[str, list[ExampleRecord]],
    *,
    examples_per_label: int,
    rng: random.Random,
) -> dict[str, list[ExampleRecord]]:
    normalized: dict[str, list[ExampleRecord]] = {}
    for label, examples in sorted(label_to_examples.items()):
        pool = list(examples)
        if not pool:
            continue
        if len(pool) < examples_per_label:
            log_step(
                f"Label '{label}' has only {len(pool)} source examples; repeating examples to reach {examples_per_label}."
            )
            while len(pool) < examples_per_label:
                pool.append(rng.choice(examples))
        normalized[label] = pool[:examples_per_label]
    return normalized


def build_label_example_pools(
    config: SyntheticParagraphGenerationConfig,
    *,
    rng: random.Random,
) -> tuple[dict[str, list[ExampleRecord]], dict[str, int], int, list[str]]:
    label_to_examples: dict[str, list[ExampleRecord]] = {}
    seen_per_label: dict[str, int] = {}
    total_loaded = 0
    source_texts: list[str] = []
    desired_labels = {
        str(label).strip()
        for label in (config.sampling.desired_target_labels or [])
        if str(label).strip()
    }

    for path_str in config.data.source_paths:
        path = Path(path_str)

        if path.suffix == ".jsonl":
            rows = iter_jsonl_rows(path)
        elif path.suffix == ".txt":
            rows = (
                {
                    config.data.text_field: text,
                    config.data.labels_field: normalize_bio_labels(labels),
                    "sample_id": f"{path.stem}-{i}",
                }
                for i, (text, labels) in enumerate(parse_bio_paragraphs(path))
            )
        else:
            continue

        for index, row in enumerate(rows):
            if (
                config.data.max_examples is not None
                and total_loaded >= config.data.max_examples
            ):
                if not desired_labels:
                    break
                desired_filled = all(
                    len(label_to_examples.get(label, []))
                    >= config.data.examples_per_label
                    for label in desired_labels
                )
                if desired_filled:
                    break
                if total_loaded == config.data.max_examples:
                    log_step(
                        "Reached data.max_examples before filling desired_target_labels; continuing to scan source_path until those label pools are filled or EOF is reached."
                    )
            example = parse_example_row(
                row,
                index=index,
                text_field=config.data.text_field,
                labels_field=config.data.labels_field,
            )

            if example is None:
                continue

            total_loaded += 1
            source_texts.append(example.text)
            for label in example.labels:
                seen_per_label[label] = seen_per_label.get(label, 0) + 1
                reservoir = label_to_examples.setdefault(label, [])

                if len(reservoir) < config.data.examples_per_label:
                    reservoir.append(example)
                else:
                    draw = rng.randint(1, seen_per_label[label])
                    if draw <= config.data.examples_per_label:
                        reservoir[draw - 1] = example

    normalized = ensure_exact_examples_per_label(
        label_to_examples,
        examples_per_label=config.data.examples_per_label,
        rng=rng,
    )
    if not normalized:
        raise ValueError(
            "No labeled source examples could be sampled from data.source_path."
        )
    return normalized, seen_per_label, total_loaded, source_texts


def load_guidelines(path: str | None) -> str:
    if not path:
        return "Write realistic, coherent legal paragraphs in Rioplatense Spanish."
    content = Path(path).read_text(encoding="utf-8").strip()
    return (
        content or "Write realistic, coherent legal paragraphs in Rioplatense Spanish."
    )


def discover_available_labels(
    label_example_pools: dict[str, list[ExampleRecord]],
    *,
    augmentation_functions: dict[str, Any],
    llm_only_labels: set[str],
) -> list[str]:
    supported = set(augmentation_functions) | llm_only_labels
    labels = sorted(set(label_example_pools) & supported)
    if not labels:
        raise ValueError("No available labels remain after applying support filters.")
    return labels


def choose_primary_target_label(
    available_labels: list[str],
    *,
    desired_target_labels: list[str] | None,
    desired_index: int,
    generated_counts_by_desired_label: dict[str, int],
    per_label_target: int,
    rng: random.Random,
) -> str | None:
    if desired_target_labels:
        desired = [
            label for label in desired_target_labels if label in available_labels
        ]
        if not desired:
            return None
        remaining = [
            label
            for label in desired
            if generated_counts_by_desired_label.get(label, 0) < per_label_target
        ]
        if not remaining:
            return None
        return remaining[desired_index % len(remaining)]
    if not available_labels:
        return None
    return rng.choice(available_labels)


def expand_labels_from_example_structure(
    primary_label: str,
    *,
    label_example_pools: dict[str, list[ExampleRecord]],
    available_labels: list[str],
) -> list[str]:
    available_set = set(available_labels)
    examples = label_example_pools.get(primary_label, [])
    expanded = {primary_label}
    for example in examples:
        for label in example.labels:
            if label in available_set:
                expanded.add(label)
    return sorted(expanded)


def count_tokens(text: str, *, encoding_name: str) -> int:
    try:
        import tiktoken

        try:
            encoder = tiktoken.get_encoding(encoding_name)
        except Exception:  # noqa: BLE001
            encoder = tiktoken.get_encoding("cl100k_base")
        return len(encoder.encode(text))
    except Exception:  # noqa: BLE001
        return max(1, len(text) // 4)


def build_examples_block(label_examples: dict[str, list[ExampleRecord]]) -> str:
    lines: list[str] = []
    for label in sorted(label_examples):
        lines.append(f"Label: {label}")
        for idx, example in enumerate(label_examples[label], start=1):
            lines.append(f"Example {idx} | sample_id={example.sample_id}")
            lines.append(example.text)
            lines.append("")
    return "\n".join(lines).strip()


def build_user_prompt(
    *,
    guidelines: str,
    label_examples: dict[str, list[ExampleRecord]],
    labels: list[str],
    paragraph_jobs: list[dict[str, Any]],
    llm_only_labels: list[str],
    paragraphs_per_call: int,
) -> str:
    return LLM_USER_PROMPT_TEMPLATE.format(
        guidelines=guidelines,
        examples_block=build_examples_block(label_examples),
        labels_json=json.dumps(labels, ensure_ascii=False, indent=2),
        paragraph_jobs_json=json.dumps(paragraph_jobs, ensure_ascii=False, indent=2),
        llm_only_labels_json=json.dumps(llm_only_labels, ensure_ascii=False, indent=2),
        paragraphs_per_call=paragraphs_per_call,
    )


def build_candidate_map_for_labels(
    labels: list[str],
    *,
    augmentation_functions: dict[str, Any],
    augmentation_faker: Any,
    config: SyntheticParagraphGenerationConfig,
    rng: random.Random,
) -> tuple[dict[str, str], list[str], dict[str, list[str]]]:
    candidate_map, missing_labels = generate_label_candidates(
        labels,
        augmentation_functions=augmentation_functions,
        augmentation_faker=augmentation_faker,
        n_options=config.faker.candidates_per_label,
        max_attempts_per_label=config.faker.max_attempts_per_label,
        seed=rng.randint(1, 1_000_000),
    )
    chosen_values = {
        label: rng.choice(values) for label, values in candidate_map.items() if values
    }
    return chosen_values, missing_labels, candidate_map


def build_paragraph_jobs_for_batch(
    labels: list[str],
    *,
    augmentation_functions: dict[str, Any],
    augmentation_faker: Any,
    config: SyntheticParagraphGenerationConfig,
    rng: random.Random,
    paragraphs_per_call: int,
) -> tuple[list[dict[str, Any]], list[str], dict[str, list[str]]]:
    paragraph_jobs: list[dict[str, Any]] = []
    combined_missing: set[str] = set()
    candidate_map_reference: dict[str, list[str]] = {}
    for _ in range(paragraphs_per_call):
        provided_values, missing_labels, candidate_map = build_candidate_map_for_labels(
            labels,
            augmentation_functions=augmentation_functions,
            augmentation_faker=augmentation_faker,
            config=config,
            rng=rng,
        )
        candidate_map_reference = candidate_map
        combined_missing.update(missing_labels)
        paragraph_jobs.append(
            {
                "job_id": uuid.uuid4().hex,
                "provided_values": provided_values,
            }
        )
    return paragraph_jobs, sorted(combined_missing), candidate_map_reference


def locate_entities(text: str, entities: list[dict[str, str]]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []
    for entity in entities:
        label = str(entity["label"]).strip()
        value = str(entity["value"]).strip()
        if not label or not value:
            raise ValueError(f"Invalid entity payload: {entity}")
        start = text.find(value)
        if start == -1:
            raise ValueError(
                f"Could not find entity value '{value}' for label '{label}' in generated paragraph."
            )
        if text.find(value, start + 1) != -1:
            raise ValueError(
                f"Entity value '{value}' for label '{label}' appears more than once in generated paragraph."
            )
        end = start + len(value)
        for existing_start, existing_end in spans:
            if not (end <= existing_start or start >= existing_end):
                raise ValueError(
                    f"Overlapping entity spans detected for value '{value}'."
                )
        spans.append((start, end))
        resolved.append(
            {
                "label": label,
                "text": value,
                "start_char": start,
                "end_char": end,
            }
        )
    return sorted(resolved, key=lambda item: (item["start_char"], item["end_char"]))


def fit_prompt_batch(
    *,
    labels: list[str],
    label_example_pools: dict[str, list[ExampleRecord]],
    guidelines: str,
    paragraph_jobs: list[dict[str, Any]],
    missing_labels: list[str],
    config: SyntheticParagraphGenerationConfig,
) -> PromptBatch:
    max_prompt_tokens = max(
        1, config.llm.max_context_tokens - config.llm.reserved_output_tokens
    )
    reduced_examples_per_label = {
        label: config.data.examples_per_label for label in labels
    }

    while True:
        label_examples = {
            label: label_example_pools[label][: reduced_examples_per_label[label]]
            for label in labels
        }
        prompt = build_user_prompt(
            guidelines=guidelines,
            label_examples=label_examples,
            labels=labels,
            paragraph_jobs=paragraph_jobs,
            llm_only_labels=missing_labels,
            paragraphs_per_call=len(paragraph_jobs),
        )
        prompt_token_count = count_tokens(
            LLM_SYSTEM_PROMPT + "\n\n" + prompt,
            encoding_name=config.llm.token_encoding_name,
        )
        if prompt_token_count <= max_prompt_tokens:
            return PromptBatch(
                labels=labels,
                prompt=prompt,
                prompt_token_count=prompt_token_count,
                paragraph_jobs=paragraph_jobs,
                missing_labels=missing_labels,
                reference_examples=label_examples,
                reduced_examples_per_label=dict(reduced_examples_per_label),
            )

        if len(labels) != 1:
            raise ValueError("Prompt overflow requires batching across target labels.")

        label = labels[0]
        if reduced_examples_per_label[label] <= 1:
            raise ValueError(
                f"Single-label batch for '{label}' still exceeds context with one example."
            )
        reduced_examples_per_label[label] -= 1
        log_step(
            f"Reducing examples_per_label for batch label '{label}' to {reduced_examples_per_label[label]} due to context overflow."
        )


def build_prompt_batches(
    *,
    target_labels: list[str],
    label_example_pools: dict[str, list[ExampleRecord]],
    guidelines: str,
    paragraph_jobs: list[dict[str, Any]],
    missing_labels: list[str],
    config: SyntheticParagraphGenerationConfig,
) -> list[PromptBatch]:
    if not target_labels:
        return []

    batches: list[PromptBatch] = []
    current_labels: list[str] = []

    for label in target_labels:
        tentative_labels = current_labels + [label]
        tentative_jobs = [
            {
                "job_id": job["job_id"],
                "provided_values": {
                    key: value
                    for key, value in job["provided_values"].items()
                    if key in tentative_labels
                },
            }
            for job in paragraph_jobs
        ]
        tentative_missing = [
            item for item in missing_labels if item in tentative_labels
        ]
        try:
            fit_prompt_batch(
                labels=tentative_labels,
                label_example_pools=label_example_pools,
                guidelines=guidelines,
                paragraph_jobs=tentative_jobs,
                missing_labels=tentative_missing,
                config=config,
            )
            current_labels = tentative_labels
        except ValueError as exc:
            if current_labels:
                batch_jobs = [
                    {
                        "job_id": job["job_id"],
                        "provided_values": {
                            key: value
                            for key, value in job["provided_values"].items()
                            if key in current_labels
                        },
                    }
                    for job in paragraph_jobs
                ]
                batch_missing = [
                    item for item in missing_labels if item in current_labels
                ]
                batches.append(
                    fit_prompt_batch(
                        labels=current_labels,
                        label_example_pools=label_example_pools,
                        guidelines=guidelines,
                        paragraph_jobs=batch_jobs,
                        missing_labels=batch_missing,
                        config=config,
                    )
                )
                current_labels = [label]
            else:
                log_step(
                    f"Switching to single-label fallback for '{label}' because the combined prompt exceeded context: {exc}"
                )
                current_labels = [label]

    if current_labels:
        batch_jobs = [
            {
                "job_id": job["job_id"],
                "provided_values": {
                    key: value
                    for key, value in job["provided_values"].items()
                    if key in current_labels
                },
            }
            for job in paragraph_jobs
        ]
        batch_missing = [item for item in missing_labels if item in current_labels]
        batches.append(
            fit_prompt_batch(
                labels=current_labels,
                label_example_pools=label_example_pools,
                guidelines=guidelines,
                paragraph_jobs=batch_jobs,
                missing_labels=batch_missing,
                config=config,
            )
        )

    if len(batches) > 1:
        log_step(
            f"Context overflow detected; switched to batch mode for labels {target_labels} -> {[batch.labels for batch in batches]}"
        )
    return batches


def generate_paragraph_with_llm(
    *,
    prompt: str,
    config: SyntheticParagraphGenerationConfig,
) -> tuple[dict[str, Any], str, int]:
    from aymurai.llm_providers import OllamaLLMProvider

    prompt_token_count = count_tokens(
        LLM_SYSTEM_PROMPT + "\n\n" + prompt,
        encoding_name=config.llm.token_encoding_name,
    )

    provider = OllamaLLMProvider(
        model=config.llm.model,
        keep_alive=config.llm.keep_alive,
    )
    response = provider.generate(
        messages=[
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        options={
            "temperature": config.llm.temperature,
            "num_ctx": config.llm.num_ctx,
        },
        format=SyntheticParagraphBatchResponse.model_json_schema(),
    )
    payload = json.loads(response.text)
    return payload, response.text, prompt_token_count


def prepare_run_dir(config: SyntheticParagraphGenerationConfig) -> Path:
    run_dir_name = render_run_dir_name(config.outputs.run_dir_name_template)
    run_dir = Path(config.outputs.base_dir) / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def passes_similarity_check(
    text: str,
    *,
    normalized_reference_texts: list[str],
    reference_texts: list[str],
    threshold: float,
) -> tuple[bool, dict[str, Any] | None]:
    processed_text = normalize_text_for_match(text)
    match = extract_one_match(
        processed_text,
        normalized_reference_texts,
        score_cutoff=threshold,
    )
    if not match:
        return True, None
    _, score, index = match
    return False, {
        "similarity_score": score,
        "matched_with": reference_texts[index],
    }


def load_similarity_reference_texts(
    config: SyntheticParagraphGenerationConfig,
    *,
    source_texts: list[str],
) -> tuple[list[str], str]:
    if not config.similarity.enabled:
        return [], "disabled"

    bio_paths = [
        config.similarity.train_set_path,
        config.similarity.dev_set_path,
        config.similarity.test_set_path,
    ]
    resolved_paths = [Path(path) for path in bio_paths if path]
    resolved_paths.extend(
        Path(path) for path in config.similarity.extra_bio_paths if path
    )
    if resolved_paths:
        corpus_texts: list[str] = []
        for path in resolved_paths:
            corpus_texts.extend(paragraphs_from_bio(path))
        return corpus_texts, "bio_corpora"

    return source_texts, "source_examples"


def append_internal_similarity_reference(
    text: str,
    *,
    internal_reference_texts: list[str],
    normalized_internal_reference_texts: list[str],
) -> None:
    internal_reference_texts.append(text)
    normalized_internal_reference_texts.append(normalize_text_for_match(text))


def run_pipeline(config: SyntheticParagraphGenerationConfig) -> dict[str, Any]:
    run_dir = prepare_run_dir(config)
    log_step(f"Writing artifacts to {run_dir}")

    rng = random.Random(config.sampling.seed)
    project_root = Path(__file__).resolve().parents[3]
    augmentation_functions, augmentation_faker = load_augmentation_registry(
        project_root
    )
    llm_only_labels = {
        label.strip() for label in config.faker.llm_only_labels if label.strip()
    }

    (
        label_example_pools,
        label_source_counts,
        total_loaded_examples,
        source_texts,
    ) = build_label_example_pools(
        config,
        rng=rng,
    )
    (
        similarity_reference_texts,
        similarity_reference_kind,
    ) = load_similarity_reference_texts(
        config,
        source_texts=source_texts,
    )
    normalized_similarity_reference_texts = [
        normalize_text_for_match(text) for text in similarity_reference_texts
    ]
    internal_similarity_reference_texts: list[str] = []
    normalized_internal_similarity_reference_texts: list[str] = []
    guidelines = load_guidelines(config.data.guidelines_path)
    available_labels = discover_available_labels(
        label_example_pools,
        augmentation_functions=augmentation_functions,
        llm_only_labels=llm_only_labels,
    )
    log_step(
        f"Loaded {total_loaded_examples} source examples and built few-shot pools for {len(available_labels)} labels"
    )
    if config.sampling.desired_target_labels:
        log_step(
            "desired_target_labels configured; the runner will search examples for those labels "
            "and call the LLM separately for each selected target label. If those examples contain "
            "other supported labels, they will also be included, generated, and annotated so the "
            "synthetic paragraph keeps a realistic structure."
        )
        log_step(
            f"target_total_synthetic will be applied per desired label: "
            f"{config.sampling.target_total_synthetic} paragraph(s) for each desired target label."
        )
    log_step(
        f"Configured to generate {config.llm.paragraphs_per_call} synthetic paragraph(s) per LLM call"
    )

    records: list[dict[str, Any]] = []
    prompt_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    label_counter: Counter[str] = Counter()
    generated_counts_by_desired_label: dict[str, int] = {
        str(label).strip(): 0
        for label in (config.sampling.desired_target_labels or [])
        if str(label).strip()
    }
    per_label_target = config.sampling.target_total_synthetic
    total_target_synthetic = (
        per_label_target * len(generated_counts_by_desired_label)
        if generated_counts_by_desired_label
        else config.sampling.target_total_synthetic
    )
    total_attempt_cycles = 0
    desired_target_index = 0
    max_attempt_cycles = max(
        total_target_synthetic * (config.llm.max_retries_per_sample + 2) * 5,
        25,
    )

    progress = tqdm(
        total=total_target_synthetic,
        desc="generate-synthetic",
    )

    while (
        len(records) < total_target_synthetic
        and total_attempt_cycles < max_attempt_cycles
    ):
        total_attempt_cycles += 1
        desired_target_label: str | None = None
        example_structure_labels: list[str] = []

        desired_target_label = choose_primary_target_label(
            available_labels,
            desired_target_labels=[
                str(label).strip()
                for label in (config.sampling.desired_target_labels or [])
                if str(label).strip()
            ]
            or None,
            desired_index=desired_target_index,
            generated_counts_by_desired_label=generated_counts_by_desired_label,
            per_label_target=per_label_target,
            rng=rng,
        )
        if desired_target_label is None:
            break
        if config.sampling.desired_target_labels:
            desired_target_index += 1

        target_labels = [desired_target_label]
        expanded_target_labels = expand_labels_from_example_structure(
            desired_target_label,
            label_example_pools=label_example_pools,
            available_labels=available_labels,
        )
        example_structure_labels = [
            label for label in expanded_target_labels if label != desired_target_label
        ]
        if expanded_target_labels != target_labels:
            log_step(
                "Expanded desired target label from example structure: "
                f"primary={desired_target_label} -> labels={expanded_target_labels}"
            )
        target_labels = expanded_target_labels

        paragraph_jobs, missing_labels, candidate_map = build_paragraph_jobs_for_batch(
            target_labels,
            augmentation_functions=augmentation_functions,
            augmentation_faker=augmentation_faker,
            config=config,
            rng=rng,
            paragraphs_per_call=min(
                config.llm.paragraphs_per_call,
                (
                    per_label_target
                    - generated_counts_by_desired_label.get(desired_target_label, 0)
                    if desired_target_label in generated_counts_by_desired_label
                    else total_target_synthetic - len(records)
                ),
            ),
        )
        prompt_batches = build_prompt_batches(
            target_labels=target_labels,
            label_example_pools=label_example_pools,
            guidelines=guidelines,
            paragraph_jobs=paragraph_jobs,
            missing_labels=missing_labels,
            config=config,
        )

        for batch in prompt_batches:
            if len(records) >= total_target_synthetic:
                break

            success_records: list[dict[str, Any]] = []
            raw_response_text: str | None = None
            last_error: str | None = None
            actual_prompt_tokens: int | None = None
            validation_results: list[dict[str, Any]] = []

            for _attempt in range(1, config.llm.max_retries_per_sample + 2):
                try:
                    log_step(
                        "LLM call request: "
                        f"desired_target_label={desired_target_label}, "
                        f"example_structure_labels={example_structure_labels}, "
                        f"batch_labels={batch.labels}, "
                        f"jobs={len(batch.paragraph_jobs)}, "
                        f"requested_values={[job['provided_values'] for job in batch.paragraph_jobs]}"
                    )
                    (
                        payload,
                        raw_response_text,
                        actual_prompt_tokens,
                    ) = generate_paragraph_with_llm(
                        prompt=batch.prompt,
                        config=config,
                    )
                    parsed = SyntheticParagraphBatchResponse.model_validate(payload)
                    expected_job_ids = {job["job_id"] for job in batch.paragraph_jobs}
                    returned_job_ids = {item.job_id for item in parsed.paragraphs}
                    if expected_job_ids != returned_job_ids:
                        raise ValueError(
                            f"Generated job ids do not match request. expected={sorted(expected_job_ids)} actual={sorted(returned_job_ids)}"
                        )
                    job_lookup = {job["job_id"]: job for job in batch.paragraph_jobs}
                    success_records = []
                    validation_results = []
                    normalized_labels = (
                        [
                            line.strip()
                            for line in Path(config.data.normalized_labels_path)
                            .read_text(encoding="utf-8")
                            .splitlines()
                            if line.strip()
                        ]
                        if config.data.normalized_labels_path
                        and Path(config.data.normalized_labels_path).exists()
                        else batch.labels
                    )

                    for paragraph_item in parsed.paragraphs:
                        requested_job = job_lookup[paragraph_item.job_id]
                        requested_values = requested_job["provided_values"]
                        clean_paragraph = strip_label_names_from_text(
                            paragraph_item.paragraph, normalized_labels
                        )
                        log_step(f"Paragraph: '{clean_paragraph}'.")
                        entities = locate_entities(
                            clean_paragraph,
                            [
                                entity.model_dump(mode="json")
                                for entity in paragraph_item.entities
                            ],
                        )
                        log_step(f"Located entities: {entities}")
                        expected_labels = Counter(batch.labels)
                        actual_labels = Counter(entity["label"] for entity in entities)
                        if expected_labels != actual_labels:
                            raise ValueError(
                                f"Generated entity labels do not match request for job {paragraph_item.job_id}. expected={dict(expected_labels)} actual={dict(actual_labels)}"
                            )

                        exact_once_checks: dict[str, bool] = {}
                        for label, value in requested_values.items():
                            match = next(
                                (
                                    entity
                                    for entity in entities
                                    if entity["label"] == label
                                ),
                                None,
                            )
                            exact_once_checks[label] = (
                                match is not None and match["text"] == value
                            )
                            if not exact_once_checks[label]:
                                raise ValueError(
                                    f"Generated entity value for label '{label}' does not match the Faker value '{value}' in job {paragraph_item.job_id}."
                                )

                        bio_lines = entities_to_bio_lines(clean_paragraph, entities)
                        similarity_validation = {
                            "enabled": config.similarity.enabled,
                            "passed": True,
                            "details": None,
                        }
                        if config.similarity.enabled:
                            passed, details = passes_similarity_check(
                                clean_paragraph,
                                normalized_reference_texts=normalized_similarity_reference_texts,
                                reference_texts=similarity_reference_texts,
                                threshold=config.similarity.threshold,
                            )
                            similarity_validation = {
                                "enabled": True,
                                "passed": passed,
                                "details": details,
                            }
                            if not passed:
                                raise ValueError(
                                    f"Generated paragraph failed similarity check with score {details['similarity_score']:.2f}."
                                )
                        internal_similarity_validation = {
                            "enabled": config.similarity.internal_enabled,
                            "passed": True,
                            "details": None,
                        }
                        if (
                            config.similarity.internal_enabled
                            and normalized_internal_similarity_reference_texts
                        ):
                            passed, details = passes_similarity_check(
                                clean_paragraph,
                                normalized_reference_texts=normalized_internal_similarity_reference_texts,
                                reference_texts=internal_similarity_reference_texts,
                                threshold=config.similarity.internal_threshold,
                            )
                            internal_similarity_validation = {
                                "enabled": True,
                                "passed": passed,
                                "details": details,
                            }
                            if not passed:
                                raise ValueError(
                                    "Generated paragraph failed internal similarity "
                                    f"check with score {details['similarity_score']:.2f}."
                                )

                        success_records.append(
                            {
                                "sample_id": uuid.uuid4().hex,
                                "job_id": paragraph_item.job_id,
                                "text": clean_paragraph,
                                "entities": entities,
                                "bio_lines": bio_lines,
                                "desired_target_label": desired_target_label,
                                "example_structure_labels": example_structure_labels,
                                "all_generation_labels": batch.labels,
                                "target_labels": batch.labels,
                                "faker_values": requested_values,
                                "llm_only_labels": batch.missing_labels,
                                "candidate_values": {
                                    label: candidate_map.get(label, [])
                                    for label in batch.labels
                                },
                                "reference_example_ids": {
                                    label: [example.sample_id for example in examples]
                                    for label, examples in batch.reference_examples.items()
                                },
                                "examples_per_label_used": batch.reduced_examples_per_label,
                                "prompt_token_count": actual_prompt_tokens,
                                "validation": {
                                    "requested_labels": batch.labels,
                                    "requested_values": requested_values,
                                    "actual_labels": dict(actual_labels),
                                    "exact_once_checks": exact_once_checks,
                                    "all_exact_once": all(exact_once_checks.values()),
                                    "similarity": similarity_validation,
                                    "internal_similarity": internal_similarity_validation,
                                },
                                "created_at": timestamp_now(),
                            }
                        )
                        validation_results.append(
                            {
                                "job_id": paragraph_item.job_id,
                                "requested_labels": batch.labels,
                                "requested_values": requested_values,
                                "actual_labels": dict(actual_labels),
                                "exact_once_checks": exact_once_checks,
                                "all_exact_once": all(exact_once_checks.values()),
                                "similarity": similarity_validation,
                                "internal_similarity": internal_similarity_validation,
                            }
                        )
                    log_step(
                        f"LLM call validation passed for batch_labels={batch.labels}: "
                        f"{json.dumps(validation_results, ensure_ascii=False)}"
                    )
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)

            prompt_records.append(
                {
                    "sample_index": len(records),
                    "desired_target_label": desired_target_label,
                    "example_structure_labels": example_structure_labels,
                    "all_generation_labels": batch.labels,
                    "target_labels": batch.labels,
                    "paragraph_jobs": batch.paragraph_jobs,
                    "llm_only_labels": batch.missing_labels,
                    "reference_example_ids": {
                        label: [example.sample_id for example in examples]
                        for label, examples in batch.reference_examples.items()
                    },
                    "examples_per_label_used": batch.reduced_examples_per_label,
                    "prompt_token_count": batch.prompt_token_count,
                    "prompt": batch.prompt,
                    "raw_response_text": raw_response_text,
                    "last_error": last_error,
                    "validation_results": validation_results,
                }
            )

            if not success_records:
                failures.append(
                    {
                        "desired_target_label": desired_target_label,
                        "example_structure_labels": example_structure_labels,
                        "all_generation_labels": batch.labels,
                        "target_labels": batch.labels,
                        "paragraph_jobs": batch.paragraph_jobs,
                        "llm_only_labels": batch.missing_labels,
                        "error": last_error,
                    }
                )
                continue

            for success_record in success_records:
                if len(records) >= total_target_synthetic:
                    break
                if (
                    desired_target_label in generated_counts_by_desired_label
                    and generated_counts_by_desired_label[desired_target_label]
                    >= per_label_target
                ):
                    break
                records.append(success_record)
                append_internal_similarity_reference(
                    success_record["text"],
                    internal_reference_texts=internal_similarity_reference_texts,
                    normalized_internal_reference_texts=normalized_internal_similarity_reference_texts,
                )
                label_counter.update(batch.labels)
                if desired_target_label in generated_counts_by_desired_label:
                    generated_counts_by_desired_label[desired_target_label] += 1
                progress.update(1)

    progress.close()

    samples_path = run_dir / config.outputs.samples_jsonl
    bio_path = run_dir / config.outputs.bio_txt
    prompts_path = run_dir / config.outputs.prompts_jsonl
    report_path = run_dir / config.outputs.report_json

    write_jsonl(samples_path, records)
    write_jsonl(prompts_path, prompt_records)
    bio_path.write_text(
        "\n\n".join("\n".join(record["bio_lines"]) for record in records)
        + ("\n" if records else ""),
        encoding="utf-8",
    )

    report = {
        "run_dir": str(run_dir),
        "config": config.model_dump(mode="json"),
        "counts": {
            "generated_samples": len(records),
            "failed_samples": len(failures),
            "available_labels": len(available_labels),
            "source_examples_loaded": total_loaded_examples,
            "max_attempt_cycles": max_attempt_cycles,
            "attempt_cycles_used": total_attempt_cycles,
            "target_total_synthetic": total_target_synthetic,
            "target_per_desired_label": per_label_target
            if generated_counts_by_desired_label
            else None,
        },
        "few_shot_pool_sizes": {
            label: len(examples)
            for label, examples in sorted(label_example_pools.items())
        },
        "source_label_counts": dict(sorted(label_source_counts.items())),
        "similarity": {
            "enabled": config.similarity.enabled,
            "threshold": config.similarity.threshold,
            "compare_against": similarity_reference_kind,
            "reference_text_count": len(similarity_reference_texts),
            "internal_enabled": config.similarity.internal_enabled,
            "internal_threshold": config.similarity.internal_threshold,
            "internal_reference_text_count": len(internal_similarity_reference_texts),
            "train_set_path": config.similarity.train_set_path,
            "dev_set_path": config.similarity.dev_set_path,
            "test_set_path": config.similarity.test_set_path,
            "extra_bio_paths": config.similarity.extra_bio_paths,
        },
        "generated_label_counts": dict(sorted(label_counter.items())),
        "generated_counts_by_desired_label": dict(
            sorted(generated_counts_by_desired_label.items())
        ),
        "artifacts": {
            "samples_jsonl": str(samples_path),
            "bio_txt": str(bio_path),
            "prompts_jsonl": str(prompts_path),
            "report_json": str(report_path),
        },
        "failures": failures,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if len(records) < total_target_synthetic:
        log_step(
            f"Stopped early after generating {len(records)} / {total_target_synthetic} samples."
        )
    else:
        log_step(f"Generated {len(records)} synthetic paragraphs")
    log_step(f"Saved samples to {samples_path}")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate synthetic legal paragraphs with LLM + Faker."
    )
    parser.add_argument(
        "--config", required=True, help="Path to the YAML configuration file."
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = load_synthetic_paragraph_generation_config(args.config)
    run_pipeline(config)


if __name__ == "__main__":
    main()
