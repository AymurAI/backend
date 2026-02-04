import re
import unicodedata
from collections import Counter
from typing import Iterable
import copy
import json
import uuid
from functools import lru_cache
from pathlib import Path
from more_itertools import unique_everseen

from transformers import AutoTokenizer

from rapidfuzz import process
from rapidfuzz.fuzz import token_set_ratio

from aymurai.meta.api_interfaces import (
    DocLabel,
    DocumentAnnotations,
    PromptSet,
    PromptLibrary,
)
from aymurai.meta.entities import CanonicalEntities, CanonicalEntity
from aymurai.utils.json_data import get_pretty
from aymurai.utils.yaml_data import load_yaml
from aymurai.llm_providers import OllamaLLMProvider
from aymurai.settings import settings


__all__ = [
    "build_canonical_entities",
    "llm_canonical_entities_inference",
    "map_canonical_entities_ner_preds",
    "load_prompts_from_yaml",
]


def _cluster_with_cdist(
    *,
    items: list[dict[str, str]],
    threshold: int,
) -> list[list[tuple[str, str, str]]]:
    if not items:
        return []

    entities = [item.get("text", "") for item in items]
    labels = [item.get("aymurai_label", "UNKNOWN") for item in items]

    normed = [str(e).lower().strip() if e else "" for e in entities]

    sim = process.cdist(normed, normed, scorer=token_set_ratio, score_cutoff=threshold)

    parent = list(range(len(normed)))

    def _find(idx: int) -> int:
        if parent[idx] == idx:
            return idx
        parent[idx] = _find(parent[idx])
        return parent[idx]

    def _union(left: int, right: int) -> None:
        root_left, root_right = _find(left), _find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    n = len(normed)
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i][j] >= threshold:
                _union(i, j)

    clusters_map: dict[int, list[tuple[str, str, str]]] = {}
    for idx in range(n):
        root = _find(idx)
        clusters_map.setdefault(root, []).append(
            (entities[idx], normed[idx], labels[idx])
        )

    return list(clusters_map.values())


def _parse_item(item: tuple[str, str, str]) -> tuple[str, str, str]:
    orig, norm, label = item
    return label, orig, norm


def _pick_cluster_label(parsed_items: list[tuple[str, str, str]]) -> str:
    labels = [label for label, _, _ in parsed_items]
    return Counter(labels).most_common(1)[0][0]


def _pick_canonical_text(parsed_items: list[tuple[str, str, str]]) -> str:
    return max(parsed_items, key=lambda item: len(item[1]))[1]


def clusters_to_canonical_entities(
    clusters: list[list[tuple[str, str, str]]],
) -> list[CanonicalEntity]:
    canonical_entities = []
    for cluster in clusters:
        parsed = [_parse_item(item) for item in cluster]
        label = _pick_cluster_label(parsed)
        canonical_text = _pick_canonical_text(parsed)
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
        clusters = _cluster_with_cdist(
            items=items,
            threshold=threshold,
        )
        canonical_entities.extend(clusters_to_canonical_entities(clusters))

    canonical_entities = sorted(canonical_entities, key=lambda x: x.canonical_text)

    return canonical_entities


@lru_cache(maxsize=1)
def load_prompts_from_yaml():
    path = Path(settings.RESOURCES_BASEPATH) / "llm/entity_disambiguation.yaml"
    data = load_yaml(file_path=str(path))

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
    max_context_snippets: int | None = 5,
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

    alias_to_snippets = {alias: [] for alias in aliases}
    all_snippets_deduped = []

    # context_windows = set()

    for pred in predictions:
        if not pred.labels:
            continue
        doc_text = getattr(pred, "document", "")

        for label in pred.labels:
            if entity_label and label.attrs.aymurai_label != entity_label:
                continue

            alias = label.attrs.aymurai_alt_text
            if alias not in aliases:
                continue

            snippet = _extract_snippet(doc_text, label, window_length)

            if snippet not in alias_to_snippets[alias]:
                alias_to_snippets[alias].append(snippet)

            if snippet not in all_snippets_deduped:
                all_snippets_deduped.append(snippet)

    baseline = []
    for alias in aliases:
        snippets = alias_to_snippets.get(alias, [])
        if snippets:
            baseline.append(snippets[0])

    baseline = list(unique_everseen(baseline))

    remaining = [s for s in all_snippets_deduped if s not in baseline]

    merged = baseline + remaining

    effective_limit = (
        None
        if max_context_snippets is None
        else max(max_context_snippets, len(baseline))
    )

    if effective_limit is not None:
        return merged[:effective_limit]
    else:
        return merged


def add_canonical_entities_context(
    predictions: DocumentAnnotations,
    entities: CanonicalEntities,
    context_window_length: int | None = 120,
    target_label: str | None = None,
    max_snippets_per_entity: int | None = 5,
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
        if entity.attributes is None:
            entity.attributes = {}

        current_target = target_label or entity.aymurai_label

        entity.attributes["context"] = _get_entity_context(
            predictions,
            current_target,
            list(entity.aliases),
            context_window_length,
            max_snippets_per_entity,
        )

    return entities_with_context


_TOKENIZER_CACHE = {}


def _get_model_tokens(
    system_prompt: str, user_prompt: str, tokenizer_model: str
) -> int:
    """Calculates the number of tokens using a HuggingFace tokenizer.

    Args:
        system_prompt: The instruction text for the system role.
        user_prompt: The input text from the user.
        tokenizer_model: The HuggingFace identifier or local path of the
            tokenizer to use (e.g., 'microsoft/phi-4').

    Returns:
        The total number of tokens after applying the chat template.

    Note:
        This is an approximation. Since the model is running on Ollama, the
        internal tokenizer or template processing might differ slightly from
        the HuggingFace AutoTokenizer implementation. This serves as a
        high-fidelity heuristic for batch sizing and context management.
    """
    try:
        if tokenizer_model not in _TOKENIZER_CACHE:
            _TOKENIZER_CACHE[tokenizer_model] = AutoTokenizer.from_pretrained(
                tokenizer_model
            )

        tokenizer = _TOKENIZER_CACHE[tokenizer_model]

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        full_text = tokenizer.apply_chat_template(messages, tokenize=False)
        tokens = tokenizer.encode(full_text)

        return len(tokens)

    except Exception:
        # Fallback: simple word count approximation (one word ~ 1.4 tokens)
        combined_text = f"{system_prompt} {user_prompt}"
        word_count = len(combined_text.split())

        approx_tokens = int(word_count * 1.4) + 20

        return approx_tokens


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

            num_tokens = _get_model_tokens(
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

        len_tokens = _get_model_tokens(
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

    canonical_entities_llm = [
        CanonicalEntity.model_validate(e) for e in all_raw_outputs
    ]

    return canonical_entities_llm


def map_canonical_entities_ner_preds(
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
