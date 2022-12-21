import re
import unicodedata
from copy import deepcopy

import spacy
from spacy.tokens import Span

from aymurai.meta.pipeline_interfaces import Transform
from aymurai.spacy.components.fuzzy import FuzzyMatcher


class TextNormalize(Transform):
    def __call__(self, item: dict) -> dict:
        if not item.get("data"):
            item["data"] = {}

        item["data"]["doc.text"] = document_normalize(item["data"]["doc.text"])
        return item


class JunkCleaner(Transform):
    def __init__(self, patterns: list[str]):
        global __nlp
        __nlp = spacy.blank("es")
        self.matcher = FuzzyMatcher(__nlp.vocab)
        self.matcher.add("junk", [__nlp.make_doc(p) for p in patterns])

    def __call__(self, item: dict) -> dict:
        item = deepcopy(item)

        text = item["data"]["doc.text"]
        doc = __nlp(text)
        matches = self.matcher(doc)
        matches = sorted(matches, key=lambda x: x[1], reverse=True)
        for match in matches:
            span = Span(doc, match[1], match[2])
            start, end = span.start_char, span.end_char
            text = text[:start] + text[end:]

        item["data"]["doc.text"] = text

        return item


def document_normalize(text: str) -> str:
    """Normalize extracted text from documents
    * join invalid newlines
    * remove continous whitespaces

    Args:
        text (str): document

    Returns:
        str: normalized
    """

    # normalize character encodings
    # text = unicodedata.normalize("NFKD", text)
    text = unicodedata.normalize("NFKC", text)

    # remove continous whitespace
    text = re.sub(r" {2,}", r" ", text)

    # delete newline if NEXT char is:
    # - lower character or a number
    # - punctuanion
    text = re.sub(r"\n([a-z0-9;:,\.])", r" \g<1>", text)

    # delete newline if PREVIOUS char is:
    # - quote mark
    # - punctuanions (except '.' because possible ambiguity)
    text = re.sub(r"([\w,\"-])\n", r"\g<1> ", text)

    # cleanup some junk
    # - multiple newlines, hyphens
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[-]{2,}", "-", text)
    text = re.sub(r"\.-", ".", text)

    # quotation marks
    text = re.sub(r"(“|”)", '"', text)

    return text
