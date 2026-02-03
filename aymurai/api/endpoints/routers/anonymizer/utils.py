import re
import unicodedata
from collections import Counter
from typing import Callable, Iterable
import copy
import json
import uuid
import yaml
from functools import lru_cache
from pathlib import Path

from transformers import AutoTokenizer

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

from aymurai.meta.api_interfaces import (
    DocLabel,
    DocumentAnnotations,
    PromptSet,
    PromptLibrary,
)
from aymurai.meta.entities import CanonicalEntities, CanonicalEntity
from aymurai.utils.json_data import get_pretty
from aymurai.llm_providers import OllamaLLMProvider


__all__ = [
    "SCORER_MAP",
    "PROCESSOR_MAP",
    "build_canonical_entities",
    "resolve_processor",
    "validate_canonical_entities",
    "llm_canonical_entities_inference",
    "map_canonical_entities_NER_preds",
    "load_prompts_from_yaml",
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


def resolve_processor(name: str) -> Callable[[str], str] | None:
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
    scorer: Callable[[str, str], float],
    processor: Callable[[str], str] | None,
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
    scorer: Callable[[str, str], float],
    processor: Callable[[str], str] | None,
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

    canonical_entities = sorted(canonical_entities, key=lambda x: x.canonical_text)

    return canonical_entities


@lru_cache(maxsize=1)
def load_prompts_from_yaml():
    path = Path(__file__).parent / "prompt_templates.yaml"
    if not path.exists():
        return PromptLibrary(root=[])

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    prompts = []
    for label, content in data.items():
        prompts.append(
            PromptSet(
                label=label,
                system=content.get("system", ""),
                user=content.get("user", ""),
            )
        )
    return PromptLibrary(root=prompts)


def validate_canonical_entities(
    canonical_entities_raw: CanonicalEntities, target_label: str | None = None
) -> CanonicalEntities:
    """Validates and filters raw canonical entities for consistency.

    Args:
        canonical_entities_raw: The collection of entities as initially
            grouped by the pre-clustering algorithm.
        target_label: Optional target label (e.g., 'PER') to filter the
            results. If provided, only entities of this type will be
            returned.

    Returns:
        CanonicalEntities: A cleaned and validated collection of entities,
            ready for context assignment and further processing.
    """

    if target_label:
        entities = [
            e for e in canonical_entities_raw if e.aymurai_label == target_label
        ]
    else:
        entities = canonical_entities_raw

    validated_entities = []

    for entity in entities:
        obj = CanonicalEntity.model_validate(entity)
        if obj.entity_id is None:
            obj.entity_id = uuid.uuid4()

        validated_entities.append(obj)

    return validated_entities


def _extract_snippet(
    doc_text: str, label: list[DocLabel], window_length: int | None
) -> str:
    """
    Helper function: Extracts and cleans a text snippet surrounding a specific label.

    Args:
        doc_text: The raw text of the document or paragraph.
        label: The specific label object containing start and end character offsets.
        window_length: The number of characters to include before and after
            the label. If None, returns the `doc_text` as is.

    Returns:
        str: The extracted text snippet containing the entity and its context.
    """

    if window_length is None:
        return " ".join(doc_text.split())

    start, end = label.start_char, label.end_char
    window_start = max(0, start - window_length)
    window_end = min(len(doc_text), end + window_length)

    snippet = doc_text[window_start:window_end]
    return " ".join(snippet.split())


def _get_entity_context(
    predictions: DocumentAnnotations,
    entity_label: str,
    aliases: list[str],
    window_length: int | None,
) -> list[str]:
    """
    Helper function: Finds all context windows for a specific entity across all predictions.

    Args:
        predictions: The document annotations to search within.
        entity_label: The NER label category (e.g., 'PER').
        aliases: A list of name variants or strings associated with the entity.
        window_length: The size of the text window to extract around each match.

    Returns:
        list[str]: A list of unique text snippets providing context for the entity.
    """

    context_windows = set()

    for pred in predictions:
        if not pred.labels:
            continue
        doc_text = getattr(pred, "document", "")

        for label in pred.labels:
            if entity_label and label.attrs.aymurai_label != entity_label:
                continue
            if label.attrs.aymurai_alt_text not in aliases:
                continue

            snippet = _extract_snippet(doc_text, label, window_length)
            context_windows.add(snippet)

    return list(context_windows)


def add_canonical_entities_context(
    predictions: DocumentAnnotations,
    entities: CanonicalEntities,
    context_window_length: int | None = 120,
    target_label: str | None = None,
) -> CanonicalEntities:
    """
    Orchestrates the context enrichment for canonical entities.

    Args:
        predictions: The full document annotations containing the source
            text and label positions.
        entities: The collection of canonical entities (pre-clustered)
            to be enriched with context.
        context_window_length: The number of characters to capture around
            each mention. If None, the entire containing paragraph is used.
        target_label: Optional filter to only process entities of a
            specific type (e.g., 'PER').

    Returns:
        CanonicalEntities: The input entities enriched with a list of
            contextual snippets for each group.
    """

    entities_with_context = copy.deepcopy(entities)

    for entity in entities_with_context:
        # NOTE: Ensure attributes and context are initialized
        if entity.attributes is None:
            entity.attributes = {}

        current_target = target_label or entity.aymurai_label

        # NOTE: Extracted logic to find context
        entity.attributes["context"] = _get_entity_context(
            predictions, current_target, list(entity.aliases), context_window_length
        )

    return entities_with_context


def get_model_tokens(system_prompt: str, user_prompt: str, tokenizer_model: str) -> int:

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_model)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    full_text = tokenizer.apply_chat_template(messages, tokenize=False)
    tokens = tokenizer.encode(full_text)

    return len(tokens)


def llm_canonical_entities_inference(
    paragraphs: DocumentAnnotations,
    canonical_entities_pre_cluster: CanonicalEntities,
    system_prompt: str,
    user_prompt_template: str,
    model: str,
    tokenizer_model: str,
    target_label: str,
    context_window_length: int | None = 120,
    model_context: int = 9_500,
    token_limit_frac: float = 2 / 3,
    temperature: int = 0,
    decompose_by: int | None = 0,
) -> CanonicalEntities:

    """
    Refines pre-clustered entities into canonical forms using LLM inference.


    Args:
        paragraphs: The full document annotations containing the text and metadata
            used to extract context for each entity mention.
        canonical_entities_pre_cluster: The initial grouping of entities
            generated by the fuzzy matching phase.
        system_prompt: The instruction set defining the LLM's persona and
            extraction rules.
        user_prompt_template: The template used to format entity mentions and
            their context for the model.
        model: Identifier of the LLM to be used (e.g., 'phi4:14b').
        tokenizer_model: Name or path of the tokenizer used to calculate
            token counts for context window management.
        target_label: The specific entity label (e.g., 'PER') currently being
            processed for disambiguation.
        context_window_length: The number of characters to include around each
            mention. If None, the entire paragraph is used.
        model_context: Total token capacity of the LLM's context window.
        token_limit_frac: The safe working percentage of the `model_context`
            to avoid truncation during inference.
        temperature: Sampling temperature for the model; defaults to 0 for
            deterministic output.
        decompose_by: The fixed number of entities to process per batch.
            If 0 or None, the function may attempt to find an optimal batch size.

    Returns:
        CanonicalEntities: A curated collection of entities with resolved
            canonical names and assigned roles as determined by the LLM.
    """

    canonical_entities_with_context = add_canonical_entities_context(
        predictions=paragraphs,
        entities=canonical_entities_pre_cluster,
        context_window_length=context_window_length,
        target_label=target_label,
    )

    canonical_entities_prompt = [
        ce.model_dump(include={"canonical_text", "aliases", "attributes"})
        for ce in canonical_entities_with_context
    ]

    token_limit = int(model_context * token_limit_frac)

    if decompose_by is None:
        # NOTE: dynamically find the maximum batch size that fits the token limit
        # by iteratively shrinking the candidate list.
        current_batch_size = len(canonical_entities_prompt)

        while current_batch_size > 0:
            test_batch = canonical_entities_prompt[:current_batch_size]
            test_prompt = user_prompt_template.format(
                canonical_entities=get_pretty(test_batch)
            )

            num_tokens = get_model_tokens(
                system_prompt=system_prompt,
                user_prompt=test_prompt,
                tokenizer_model=tokenizer_model,
            )

            if num_tokens <= token_limit:
                decompose_by = current_batch_size
                break

            current_batch_size -= 1

        if not decompose_by:
            # NOTE: returns None if even a single entity exceeds the token limit.
            return None

    if decompose_by <= 0:
        entity_batches = [canonical_entities_prompt]
    else:
        entity_batches = [
            canonical_entities_prompt[i : i + decompose_by]
            for i in range(0, len(canonical_entities_prompt), decompose_by)
        ]

    all_raw_outputs = []
    all_user_prompts = []

    for batch_index, batch in enumerate(entity_batches):
        user_prompt = user_prompt_template.format(
            canonical_entities=get_pretty(batch),
        )

        all_user_prompts.append(user_prompt)

        len_tokens = get_model_tokens(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tokenizer_model=tokenizer_model,
        )
        if len_tokens > model_context:
            # NOTE: skip batches that exceed physical context window to prevent LLM hallucination or crash.
            continue

        provider = OllamaLLMProvider(model=model)
        response = provider.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": temperature, "num_ctx": model_context},
            format=CanonicalEntities.model_json_schema(),
        )

        batch_entities = json.loads(response.text).get("canonical_entities", [])
        all_raw_outputs.extend(batch_entities)

    canonical_entities_llm = validate_canonical_entities(
        canonical_entities_raw=all_raw_outputs
    )

    return canonical_entities_llm


def map_canonical_entities_NER_preds(
    predictions: DocumentAnnotations,
    canonical_entities: CanonicalEntities,
) -> DocumentAnnotations:

    """
    Syncs LLM-inferred canonical entities with original NER predictions.

    Args:
        predictions: The original list of document annotations and NER
            predictions to be updated.
        canonical_entities: The curated collection of entities containing
            the resolved canonical names and roles provided by the LLM.

    Returns:
        DocumentAnnotations: The enriched predictions, where each entity
            mention now includes a 'canonical_entity_id' and its
            corresponding 'role' when applicable.
    """

    predictions_llm = copy.deepcopy(predictions)

    new_ids_map = {}

    for document in predictions_llm:
        if not document.labels:
            continue

        for label in document.labels:
            if (
                label.attrs.canonical_entity_id is None
                and len(label.attrs.aymurai_label_subclass) == 0
            ):
                for ce in canonical_entities:
                    if label.attrs.aymurai_label == ce.aymurai_label:
                        entity_id = ce.entity_id
                        attributes = ce.attributes or {}
                        role = attributes.get("role")
                        aliases = ce.aliases

                        clean_aliases = [str(a).strip().lower() for a in aliases]
                        label_text = str(label.attrs.aymurai_alt_text).strip().lower()

                        if label_text in clean_aliases:
                            label.attrs.canonical_entity_id = entity_id
                            if ce.aymurai_label == "PER" and role is not None:
                                label.attrs.aymurai_label_subclass.append(role)
                            break

                if label.attrs.canonical_entity_id is None:
                    key = (
                        label.attrs.aymurai_label,
                        str(label.attrs.aymurai_alt_text).strip(),
                    )
                    if key not in new_ids_map:
                        new_ids_map[key] = uuid.uuid4()

                    label.attrs.canonical_entity_id = new_ids_map[key]

    return predictions_llm
