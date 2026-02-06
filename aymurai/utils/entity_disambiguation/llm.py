import copy
import json
from functools import lru_cache
from pathlib import Path

from more_itertools import unique_everseen
from transformers import AutoTokenizer

from aymurai.llm_providers import OllamaLLMProvider
from aymurai.meta.api_interfaces import (
    DocLabel,
    DocumentAnnotations,
    PromptLibrary,
    PromptSet,
)
from aymurai.meta.entities import CanonicalEntities, CanonicalEntity
from aymurai.settings import settings
from aymurai.utils.json_data import get_pretty
from aymurai.utils.yaml_data import load_yaml


@lru_cache(maxsize=1)
def load_prompts_from_yaml():
    """
    Loads and caches LLM prompt templates from the resources directory.

    Returns:
        PromptLibrary: The loaded prompt library.
    """
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


def _extract_snippet(doc_text: str, label: DocLabel, window_length: int | None) -> str:
    """
    Extracts and normalizes a text snippet around a label span.

    Args:
        doc_text (str): Full document text.
        label (DocLabel): Label containing span offsets.
        window_length (int | None): Number of characters to include around
            the label. If None, returns the full document text.

    Returns:
        str: The extracted and normalized snippet.
    """

    if window_length is None:
        return " ".join(doc_text.split())

    start, end = label.start_char, label.end_char
    window_start = max(0, start - window_length)
    window_end = min(len(doc_text), end + window_length)

    # Expand to word boundaries to avoid truncating leading/trailing words.
    while window_start > 0 and not doc_text[window_start - 1].isspace():
        window_start -= 1
    while window_end < len(doc_text) and not doc_text[window_end - 1].isspace():
        window_end += 1

    snippet = doc_text[window_start:window_end]
    return " ".join(snippet.split())


def _iter_alias_snippets(
    predictions: DocumentAnnotations,
    *,
    entity_label: str,
    aliases_set: set[str],
    window_length: int | None,
):
    """
    Yields (alias, snippet) pairs for labels matching the target entity label.

    Args:
        predictions (DocumentAnnotations): Document annotations to scan.
        entity_label (str): Target NER label to match.
        aliases_set (set[str]): Alias set to filter matches.
        window_length (int | None): Window length for snippet extraction.

    Yields:
        tuple[str, str]: (alias, snippet) pairs in appearance order.
    """
    for pred in predictions:
        if not pred.labels:
            continue
        doc_text = getattr(pred, "document", "")

        for label in pred.labels:
            if label.attrs.aymurai_label != entity_label:
                continue

            alias = label.attrs.aymurai_alt_text or label.text
            if alias not in aliases_set:
                continue

            snippet = _extract_snippet(doc_text, label, window_length)
            yield alias, snippet


def _collect_entity_context(
    predictions: DocumentAnnotations,
    entity_label: str,
    aliases: list[str],
    window_length: int | None,
    max_context_snippets: int | None = 5,
) -> list[str]:
    """
    Collects unique context snippets for aliases, preserving appearance order.

    Args:
        predictions (DocumentAnnotations): Document annotations to search within.
        entity_label (str): NER label category to match (e.g., "PER").
        aliases (list[str]): Aliases to match against label text.
        window_length (int | None): Characters to include around each match.
        max_context_snippets (int | None): Max number of snippets to return.
            If None, returns all unique snippets. Defaults to 5.

    Returns:
        list[str]: Ordered, deduplicated context snippets.
    """
    aliases_set = set(aliases)

    deduped_in_order = list(
        unique_everseen(
            _iter_alias_snippets(
                predictions,
                entity_label=entity_label,
                aliases_set=aliases_set,
                window_length=window_length,
            ),
            key=lambda item: item[1],
        )
    )

    # baseline in appearance order: first snippet per alias
    seen_aliases: set[str] = set()
    baseline = [
        snippet
        for alias, snippet in deduped_in_order
        if not (alias in seen_aliases or seen_aliases.add(alias))
    ]

    # remaining snippets in appearance order
    baseline_set = set(baseline)
    remaining = [
        snippet for _, snippet in deduped_in_order if snippet not in baseline_set
    ]

    merged = baseline + remaining

    effective_limit = (
        None
        if max_context_snippets is None
        else max(max_context_snippets, len(baseline))
    )

    return merged if effective_limit is None else merged[:effective_limit]


def _add_canonical_entities_context(
    predictions: DocumentAnnotations,
    entities: CanonicalEntities,
    context_window_length: int | None = 120,
    target_label: str | None = None,
    max_snippets_per_entity: int | None = 5,
) -> CanonicalEntities:
    """
    Attaches context snippets to each canonical entity based on predictions.

    Args:
        predictions (DocumentAnnotations): Full document annotations.
        entities (CanonicalEntities): Canonical entities to enrich with context.
        context_window_length (int | None): Characters to include around each
            mention. If None, uses the full document text.
        target_label (str | None): Optional label filter to restrict extraction.
        max_snippets_per_entity (int | None): Max snippets per entity. If None,
            returns all unique snippets.

    Returns:
        CanonicalEntities: Entities enriched with context snippets in attributes.
    """

    entities_with_context = copy.deepcopy(entities)

    for entity in entities_with_context:
        if entity.attributes is None:
            entity.attributes = {}

        current_target = target_label or entity.aymurai_label

        entity.attributes["context"] = _collect_entity_context(
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
    """
    Estimates token count for a system/user prompt using a HuggingFace tokenizer.

    Args:
        system_prompt (str): System role prompt.
        user_prompt (str): User role prompt.
        tokenizer_model (str): HuggingFace tokenizer identifier or local path.

    Returns:
        int: Approximate token count for the combined prompts.
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
        paragraphs (DocumentAnnotations): Annotated paragraphs containing labels.
        canonical_entities_pre_cluster (CanonicalEntities): Pre-clustered entities.
        system_prompt (str): System prompt for the LLM.
        user_prompt_template (str): Template for user prompt formatting.
        model (str): LLM model identifier.
        tokenizer_model (str): Tokenizer identifier for token counting.
        target_label (str): NER label to process (e.g., "PER").
        context_window_length (int | None): Context window length around mentions.
        model_context (int): Max context window size for the LLM.
        token_limit_frac (float): Fraction of model_context to use for batching.
        temperature (int): Sampling temperature.
        decompose_by (int | None): Batch size; if None, inferred.

    Returns:
        CanonicalEntities: Canonical entities refined by the LLM.
    """

    canonical_entities_with_context = _add_canonical_entities_context(
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
