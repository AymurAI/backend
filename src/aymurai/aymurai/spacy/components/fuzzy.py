import re
from functools import wraps
from typing import Any, Iterable, Optional

from spacy.pipeline import Pipe
from spacy.tokens import Doc, Span
from spacy.language import Language
from spaczz.matcher import FuzzyMatcher

from aymurai.logging import get_logger

from .utils import filter_overlapping_matches

logger = get_logger(__name__)


@Language.factory("fuzzy_ruler")
def fuzzy_ruler(
    nlp,
    name,
    patterns: list[dict[str, Any]] = None,
):
    matcher = FuzzyRuler(nlp, name=name, patterns=patterns)
    return matcher


class FuzzyRuler(Pipe):
    def __init__(
        self,
        nlp: Language,
        name: str,
        *,
        overwrite_ents: bool = False,
        patterns: Optional[list[dict[str, Any]]] = None,
    ):
        self.nlp = nlp
        self.name = name
        self.overwrite = overwrite_ents
        self.patterns = patterns

        self.matcher = FuzzyMatcher(self.nlp.vocab)

        if self.patterns:
            self.add_patterns(patterns)

    def __call__(self, doc: Doc) -> Doc:
        matches = self.matcher(doc)

        # similarity (0 to 100)
        matches = sorted(matches, key=lambda x: x[3], reverse=True)
        matches = sorted(matches, key=lambda x: x[1])
        matches = filter_overlapping_matches(matches)

        self.set_annotations(doc, matches)
        return doc

    def set_annotations(self, doc: Doc, matches: list):
        """modify document inplace"""
        for match_id, start, end, *_ in matches:
            if any(t.ent_type for t in doc[start:end]) and not self.overwrite:
                msg = "Found overlaping entity. skipping"
                logger.warn(msg)
                continue

            span = Span(doc, start, end, label=match_id)
            doc.ents += (span,)

    def add_patterns(self, patterns: list[dict[str, Any]]):
        for item in patterns:
            label = item.pop("label")
            pats = item.pop("patterns")
            pats = self.preprocess_patterns(pats)
            kwargs = [item] * len(pats)

            self.matcher.add(label=label, patterns=pats, kwargs=kwargs)
            # self.matcher.add(label=label, patterns=pats)

    def preprocess_patterns(self, patterns: Iterable[str]) -> list[Doc]:
        return [self.nlp.make_doc(token) for token in patterns]
