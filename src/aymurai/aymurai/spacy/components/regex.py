import re
from functools import wraps
from typing import Optional

from spacy.pipeline import Pipe
from spacy.tokens import Doc, Span
from spacy.language import Language
from spaczz.matcher import RegexMatcher
from datetime_matcher import DatetimeMatcher

from aymurai.logging import get_logger

from .utils import filter_overlapping_matches

logger = get_logger(__name__)


@Language.factory("enhanced_regex_ruler")
def enhanced_regex_ruler(
    nlp,
    name,
    patterns: dict[str, list[str]] = {},
):
    matcher = EnhancedRegexRuler(nlp, name=name, patterns=patterns)
    return matcher


class EnhancedRegexMatcher(RegexMatcher):
    @wraps(RegexMatcher.__init__)
    def __init__(self, *args, **kwargs):

        self.dtm = DatetimeMatcher()
        super().__init__(*args, **kwargs)

    def __call__(
        self,
        doc: Doc,
    ) -> list[tuple[str, int, int, tuple[int, int, int]]]:
        r"""
        Find all sequences matching the supplied patterns in the doc.
        patched version extending patterns with datetime

        Args:
            doc: The `Doc` object to match over.
        Returns:
            A list of (key, start, end, fuzzy change count) tuples,
            describing the matches.
        Example:
            >>> import spacy
            >>> from spaczz.matcher import RegexMatcher
            >>> nlp = spacy.blank("en")
            >>> matcher = RegexMatcher(nlp.vocab)
            >>> doc = nlp.make_doc("I live in the united states, or the US")
            >>> matcher.add("GPE", ["[Uu](nited|\.?) ?[Ss](tates|\.?)"])
            >>> matcher(doc)
            [('GPE', 4, 6, (0, 0, 0)), ('GPE', 9, 10, (0, 0, 0))]
        """
        matches = set()
        for label, patterns in self._patterns.items():
            for pattern, kwargs in zip(patterns["patterns"], patterns["kwargs"]):
                if not kwargs:
                    kwargs = self.defaults

                # patch regex patterns with datetime extension
                pattern = self.patch_pattern(pattern)

                matches_wo_label = self._searcher.match(doc, pattern, **kwargs)
                if matches_wo_label:
                    matches_w_label = [
                        (label,) + match_wo_label for match_wo_label in matches_wo_label
                    ]
                    for match in matches_w_label:
                        matches.add(match)
        if matches:
            sorted_matches = sorted(
                matches, key=lambda x: (x[1], -x[2] - x[1], sum(x[3]))
            )
            for i, (label, _start, _end, _subs) in enumerate(sorted_matches):
                on_match = self._callbacks.get(label)
                if on_match:
                    on_match(self, doc, i, sorted_matches)
            return sorted_matches
        else:
            return []

    def patch_pattern(self, pattern: str) -> str:
        """generate regex from datetime-regex format.
        Added some workarrounds to work with quasi-canonical formats.

        Args:
            fmt (str): date-regex pattern

        Returns:
            str: standard regex pattern
        """
        pattern = re.sub(r"%-?d|%-?m", r"([1-9]|\g<0>)", pattern)
        pattern = self.dtm.get_regex_from_dfregex(pattern)
        return pattern


class EnhancedRegexRuler(Pipe):
    def __init__(
        self,
        nlp: Language,
        name: str,
        *,
        overwrite_ents: bool = False,
        patterns: Optional[dict[str, list[str]]] = None,
    ):
        self.nlp = nlp
        self.name = name
        self.overwrite = overwrite_ents

        self.matcher = EnhancedRegexMatcher(nlp.vocab)
        if patterns:
            self.add_patterns(patterns)

    def __call__(self, doc: Doc) -> Doc:
        matches = self.matcher(doc)

        # Levenste
        # in dist: sum(x[3]) := sum(Substitutions, Inserts, Deletes)
        matches = sorted(matches, key=lambda x: sum(x[3]))
        matches = sorted(matches, key=lambda x: x[1])
        matches = filter_overlapping_matches(matches)

        self.set_annotations(doc, matches)
        return doc

    def set_annotations(self, doc: Doc, matches: list):
        """modify document inplace"""
        for match_id, start, end, scores in matches:
            levenstein = sum(scores)
            if any(t.ent_type for t in doc[start:end]) and not self.overwrite:
                msg = "Found overlaping entity. skipping"
                logger.warn(msg)
                continue

            span = Span(doc, start, end, label=match_id)

            # add score and method
            span._.aymurai_score = levenstein
            span._.aymurai_method = self.__class__.__name__
            # extract datetime
            patterns = filter(lambda x: x["label"] == match_id, self.patterns)
            patterns = map(lambda x: x["pattern"], patterns)
            date = map(
                lambda x: self.matcher.dtm.extract_datetime(x, doc[start:end].text),
                patterns,
            )
            date = list(filter(bool, date))
            span._.aymurai_date = date[0] if date else None

            doc.ents += (span,)

    def add_patterns(self, patterns: dict[str, list[str]]):
        for label, pats in patterns.items():
            self.matcher.add(label=label, patterns=pats)

    @property
    def patterns(self):
        return self.matcher.patterns
