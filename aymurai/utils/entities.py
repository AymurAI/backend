import pkgutil
from copy import deepcopy

import spacy

from aymurai.logging import get_logger
from aymurai.meta.api_interfaces import DocLabelAttributes

logger = get_logger(__name__)


def format_entity(entity: spacy.tokens.Span, offset: int = 10) -> dict:
    """
    Format entity to dict

    Args:
        entity (spacy.tokens.Span): entity
        offset (int, optional): context offset. Defaults to 10.

    Returns:
        dict: formatted entity in aymurai format
    """

    # start/end tokens (do not confuse with start/end characters)
    start, end = entity.start, entity.end

    soffset = max(0, start - offset)
    eoffset = min(len(entity.doc), end + offset)

    attrs = DocLabelAttributes(aymurai_label=entity.label_).dict()

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
