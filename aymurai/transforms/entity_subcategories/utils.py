import re
from copy import deepcopy

import unidecode
from more_itertools import flatten

from aymurai.utils.misc import get_element

from .article_maps import direct_map, indirect_map


def normalize_text(text: str) -> str:
    text = unidecode.unidecode(text.lower())
    text = re.sub(r"[_\-,.;:]+", "", text)
    return text


def find_subcategory_patterns(pred: str, patterns: dict) -> list:
    normalized_pred = normalize_text(pred)

    found_subcats = set()

    for subcategory, pattern in patterns.items():
        if re.search(pattern, normalized_pred):
            found_subcats.add(subcategory)

    return list(found_subcats)


def filter_by_category(ents: list[dict], category: str) -> list[dict]:
    filtered_ents = [ent for ent in ents if ent["label"] == category]
    return filtered_ents


def find_subcategories(
    ents: list[dict],
    category: str,
    patterns_dict: dict,
    use_context: bool = False,
):
    ents = deepcopy(ents)

    if use_context:
        texts = map(
            lambda x: f"{x['context_pre']} {x['text']} {x['context_post']}", ents
        )
    else:
        texts = map(lambda x: x["text"], ents)

    filtered_ents = filter_by_category(ents, category)
    found_subcats = list(
        map(lambda x: find_subcategory_patterns(x, patterns_dict), texts)
    )

    for ent, found_subcat in zip(ents, found_subcats):
        if ent in filtered_ents and not get_element(
            ent, levels=["attrs", "aymurai_label_subclass"]
        ):
            ent["attrs"]["aymurai_label_subclass"] = found_subcat

    return ents


def map_article_to_code_or_law(pred: str, ents: list[dict]) -> list[str]:
    normalized_pred = normalize_text(pred)

    conduct_ents = filter_by_category(ents, "CONDUCTA")
    conduct_subclasses = set(
        flatten(
            [
                get_element(conduct, levels=["attrs", "aymurai_label_subclass"])
                for conduct in conduct_ents
            ]
        )
    )

    for pattern, subcategory in direct_map.items():
        if re.search(pattern, normalized_pred):
            return [subcategory]

    for article, conducts in indirect_map.items():
        if re.search(article, normalized_pred):
            for conduct, subcategory in conducts.items():
                if conduct in conduct_subclasses:
                    return [subcategory]
