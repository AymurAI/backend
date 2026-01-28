import re
import unicodedata
from collections import Counter
from typing import Callable, Iterable
import copy
import json
import uuid

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

from aymurai.meta.api_interfaces import DocLabel, DocumentInformation
from aymurai.meta.entities import CanonicalEntities, CanonicalEntity
from aymurai.utils.json_data import get_pretty
from aymurai.llm_providers import OllamaLLMProvider

# from aymurai.api.endpoints.routers.anonymizer.prompt_templates import (
#     user_prompt_template_PER,
#     system_prompt_PER,
# )

__all__ = [
    "SCORER_MAP",
    "PROCESSOR_MAP",
    # "USER_PROMPT_TEMPLATE_MAP",
    # "SYSTEMP_PROMPT_MAP",
    "build_canonical_entities",
    "resolve_processor",
    "validate_canonical_entities",
    "llm_canonical_entities_inference",
    "map_canonical_entities_NER_preds",
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

# USER_PROMPT_TEMPLATE_MAP = {
#     "PER": user_prompt_template_PER
# }

# SYSTEM_PROMPT_MAP = {
#     "PER": system_prompt_PER
# }


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

    return canonical_entities


def validate_canonical_entities(
    canonical_entities_raw: list[CanonicalEntity], target_label: str | None = None
) -> list[CanonicalEntity]:

    if target_label:
        canonical_entities_val = [
            e for e in canonical_entities_raw if e.aymurai_label == target_label
        ]
    else:
        canonical_entities_val = canonical_entities_raw

    canonical_entities_val = [
        CanonicalEntity.model_validate(canonical_entity)
        for canonical_entity in canonical_entities_val
    ]

    canonical_entities_val = [
        entity.model_dump() | {"entity_id": entity.entity_id.hex}
        for entity in canonical_entities_val
    ]

    return canonical_entities_val


def add_canonical_entities_context(
    predictions: list[dict],
    entities: list[dict],
    context_window_length: int | None = 120,
    target_label: str | None = None,
) -> list[dict]:
    """
    Creates a deep copy of entities and adds context.

    Args:
        predictions: List of prediction dictionaries from the API.
        entities: List of canonical entities.
        context_window_length: Length of the window around the label. If None, full paragraph is used.
        target_label: The specific label to filter. If None, all labels are considered.
    """
    # 1. Deep copy to protect original variable
    entities_with_context = copy.deepcopy(entities)

    # 2. Process each entity
    for entity in entities_with_context:
        if "attributes" not in entity or entity["attributes"] is None:
            entity["attributes"] = {}
        if "context" not in entity["attributes"]:
            entity["attributes"]["context"] = []

        context_windows = set()
        aliases = [a for a in entity.get("aliases", [])]

        # If target_label is not provided as an argument,
        # we can default to the entity's own label if it exists
        current_target = target_label or entity.get("aymurai_label")

        # 3. Iterate through predictions
        for pred in predictions:
            doc_text = pred.document if hasattr(pred, "document") else ""
            labels = pred.labels if pred.labels is not None else []

            for label in labels:
                label_attr = label.attrs.aymurai_label
                label_text = label.text

                # Logic Gate: Filter by label type if current_target is specified
                if current_target is None or label_attr == current_target:

                    # Logic Gate: Check if any alias is inside the label text
                    if any(alias in label_text for alias in aliases):

                        # Handle Window vs Full Paragraph
                        if context_window_length is None:
                            snippet = doc_text
                        else:
                            start = label.start_char
                            end = label.end_char

                            window_start = max(0, start - context_window_length)
                            window_end = min(len(doc_text), end + context_window_length)
                            snippet = doc_text[window_start:window_end]

                        clean_snippet = " ".join(snippet.split())
                        context_windows.add(clean_snippet)

        # Update entity with the collected windows
        entity["attributes"]["context"] = list(context_windows)

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
    paragraphs: list[DocumentInformation],
    canonical_entities_pre_cluster: list[CanonicalEntity],
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
) -> dict:

    """
    Invokes the LLM to infer canonical entities by providing context to pre-clustered groups,
    while identifying the optimal batch size for processing.
    """

    # 1. First we add context to the preclustered canonical entities
    canonical_entities_with_context = add_canonical_entities_context(
        predictions=paragraphs,
        entities=canonical_entities_pre_cluster,
        context_window_length=context_window_length,
        target_label=target_label,
    )

    # 2. Clean entities to save tokens
    canonical_entities_prompt = [
        {
            k: v
            for k, v in ce.items()
            if k in ("canonical_text", "aliases", "attributes")
        }
        for ce in canonical_entities_with_context
    ]

    token_limit = int(model_context * token_limit_frac)

    # 3. Find Optimal Batch Size if decompose_by is None
    if decompose_by is None:
        current_batch_size = len(canonical_entities_prompt)

        while current_batch_size > 0:
            # Test with the first N entities
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

        if not decompose_by:  # Safety check if even 1 entity is too large
            return None

    # 4. Prepare batches. If decompose_by is 0 or less, we put all entities in one single list (one batch)
    if decompose_by <= 0:
        entity_batches = [canonical_entities_prompt]
    else:
        entity_batches = [
            canonical_entities_prompt[i : i + decompose_by]
            for i in range(0, len(canonical_entities_prompt), decompose_by)
        ]

    all_raw_outputs = []
    all_user_prompts = []

    # 5. Iterate through batches
    for batch_index, batch in enumerate(entity_batches):
        user_prompt = user_prompt_template.format(
            canonical_entities=get_pretty(batch),
        )

        all_user_prompts.append(user_prompt)

        # 5.A Token Validation
        len_tokens = get_model_tokens(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tokenizer_model=tokenizer_model,
        )
        if len_tokens > model_context:
            continue

        # 5.B LLM Inference
        provider = OllamaLLMProvider(model=model)
        response = provider.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": temperature, "num_ctx": model_context},
            format=CanonicalEntities.model_json_schema(),
        )

        # 5.C Parse and collect results
        batch_entities = json.loads(response.text).get("canonical_entities", [])
        all_raw_outputs.extend(batch_entities)

    canonical_entities_llm = validate_canonical_entities(
        canonical_entities_raw=all_raw_outputs
    )

    return {
        "canonical_entities_llm": canonical_entities_llm,
        "system_prompt": system_prompt,
        "user_prompts": all_user_prompts,
    }


def map_canonical_entities_NER_preds(
    predictions: list[DocumentInformation],
    canonical_entities: list[CanonicalEntity],
) -> list[DocumentInformation]:

    """
    Syncs LLM canonical outputs with NER predictions.
    Updates the DocumentAnnotations structure by mapping inferred entities or
    assigning a default canonical_entity_id when no match is found.
    """

    canonical_entities_val = validate_canonical_entities(
        canonical_entities_raw=canonical_entities
    )

    predictions_llm = copy.deepcopy(predictions)

    new_ids_map = {}

    for document in predictions_llm:
        if not document.labels:
            continue

        for label in document.labels:
            label_text = label.attrs.aymurai_alt_text
            if (
                label.attrs.canonical_entity_id is None
                and len(label.attrs.aymurai_label_subclass) == 0
            ):
                pred_label = label.attrs.aymurai_label
                for ce in canonical_entities_val:
                    ce_label = ce.get("aymurai_label")
                    if pred_label == ce_label:
                        entity_id = ce.get("entity_id")
                        attributes = ce.get("attributes") or {}
                        role = attributes.get("role")
                        aliases = ce.get("aliases") or []

                        if any(
                            str(alias).strip() == str(label_text).strip()
                            for alias in aliases
                        ):
                            label.attrs.canonical_entity_id = entity_id
                            if ce_label == "PER" and role is not None:
                                label.attrs.aymurai_label_subclass.append(role)
                            break

                if label.attrs.canonical_entity_id is None:
                    key = (label.attrs.aymurai_label, str(label_text).strip())
                    if key not in new_ids_map:
                        new_ids_map[key] = uuid.uuid4().hex

                    label.attrs.canonical_entity_id = new_ids_map[key]

    return predictions_llm
