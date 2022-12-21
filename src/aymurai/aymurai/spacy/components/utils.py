from itertools import chain


def filter_overlapping_matches(matches: list) -> list:
    """
    @from: https://github.com/gandersen101/spaczz/blob/c2895f6f26f2fb214fbcca1c6bcf1a24ac9f20ef/src/spaczz/search/_phrasesearcher.py#L388  # noqa

    Prevents multiple match spans from overlapping.
    Expects matches to be pre-sorted by descending ratio
    then ascending start index.
    If more than one match span includes the same tokens
    the first of these match spans in matches is kept.
    Args:
        matches: `list` of match tuples
            (match id, start index, end index, *fuzzy_scores).
    Returns:
        The filtered `list` of match span tuples.
    Example:
        >>> import spacy
        >>> from spaczz.search import _PhraseSearcher
        >>> nlp = spacy.blank("en")
        >>> searcher = _PhraseSearcher(nlp.vocab)
        >>> matches = [('id1', 1, 3, 80), ('id2', 1, 2, 70)]
        >>> searcher._filter_overlapping_matches(matches)
        [('id1', 1, 3, 80)]
    """
    filtered_matches = []
    for match in matches:
        if not set(range(match[1], match[2])).intersection(
            chain(*[set(range(n[1], n[2])) for n in filtered_matches])
        ):
            filtered_matches.append(match)
    return filtered_matches
