import os
import hashlib
import pkgutil
from pathlib import Path
from copy import deepcopy

import spacy
import srsly
from spacy.language import Language
from spacy.tokens import Span, DocBin

from aymurai.logging import get_logger
from aymurai.meta.types import DataBlock
from aymurai.spacy.components.extensions import AYMURAI_SPAN_ATTRS

SPACY_CACHE_BASEPATH = os.getenv("SPACY_CACHE_BASEPATH", "/resources/cache/spacy")

logger = get_logger(__name__)


def format_entity(entity: spacy.tokens.Span, offset: int = 10) -> dict:

    # start/end tokens (do not confuse with start/end characters)
    start, end = entity.start, entity.end

    soffset = max(0, start - offset)
    eoffset = min(len(entity.doc), end + offset)

    attrs = {attr: getattr(entity._, attr, None) for attr in AYMURAI_SPAN_ATTRS}

    return {
        "start": entity.start,
        "end": entity.end,
        "label": entity.label_,
        "text": entity.text,
        "start_char": entity.start_char,
        "end_char": entity.end_char,
        "context_pre": entity.doc[soffset : entity.start].text,
        "context_post": entity.doc[entity.end : eoffset].text,
        "attrs": attrs,
    }


def get_spacy_langs():
    langs = []
    for loader, module_name, is_pkg in pkgutil.walk_packages(spacy.lang.__path__):
        if is_pkg:
            langs.append(module_name)
    return langs


def load_base(model: str) -> spacy.language.Language:
    return spacy.blank(model) if model in get_spacy_langs() else spacy.load(model)


def load_ents(
    doc: spacy.tokens.Doc,
    entities: list[dict] = [],
    field: str = "ents",
    spans_key: str = "sc",
) -> spacy.tokens.Doc:
    """
    load entities to document (span o ents field)

    Args:
        doc (spacy.tokens.Doc): spacy document
        entities (list[dict], optional): entities. Defaults to [].
        field (str, optional): document field to add to (either `spans` or `ents`). Defaults to "ents".
        spans_key (str, optional): span key to use when field=span. Defaults to "sc".

    Returns:
        spacy.tokens.Doc: filled document
    """
    assert field in ["spans", "ents"], "field must be either `spans` or `ents`."
    # doc = doc.copy()
    doc = deepcopy(doc)
    ents = []
    for entity in entities:
        span = doc.char_span(
            entity["start_char"],
            entity["end_char"],
            label=entity["label"],
            alignment_mode="expand",
        )
        ents.append(span)

    if field == "ents":
        doc.ents += tuple(ents)
    elif field == "spans":
        if spans_key not in doc.spans:
            doc.spans[spans_key] = []
        doc.spans[spans_key] += list(ents)
    return doc


def dataset_to_docbin(
    nlp: Language,
    dataset: DataBlock,
    use_cache: bool = True,
    cache_basepath: str | Path = SPACY_CACHE_BASEPATH,
    categories: list[str] = [],
    load_ents_as_spans: bool = False,
) -> str:
    empty_cats = {cat: 0 for cat in categories}

    cache_key = hashlib.md5(srsly.json_dumps(dataset).encode("utf-8")).hexdigest()
    logger.info(f"dataset hash: {cache_key}")
    cache_path = f"{cache_basepath}/datasets/{cache_key}.spacy"
    if use_cache and Path(cache_path).exists():
        logger.info(f"loading docbin dataset from {cache_path}")
        return cache_path

    docbin = DocBin()
    for item in dataset:
        doc = nlp.make_doc(item["data"]["doc.text"])

        # setup categories
        if categories:
            item_cats = item["data"].get("doc-cats", {})
            item_cats = {k: v for k, v in item_cats.items() if k in categories}
            doc.cats = empty_cats | item_cats

        # setup entities
        if hasattr(item["data"], "entities"):
            ents = [
                Span(doc, anno["start"], anno["end"], label=anno["label"])
                for anno in item["data"]["entities"]
            ]
            if load_ents_as_spans:
                doc.spans["sc"] = ents
            else:
                doc.ents = ents

        docbin.add(doc)

    logger.info(f"saving docbin dataset on {cache_path}")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    docbin.to_disk(cache_path)

    return cache_path
