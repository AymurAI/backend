import re
from pathlib import Path
from typing import Callable
from difflib import Differ, SequenceMatcher

import numpy as np
import pandas as pd
from more_itertools import flatten

from aymurai.text.extraction import extract_document


def tokenize(text: str) -> list[str]:
    tokens = map(str.split, text.splitlines())
    tokens = flatten(tokens)
    return list(tokens)


def align_text(
    source_text: str,
    target_text: str,
    columns: tuple[str, str] = ("source", "target"),
) -> pd.DataFrame:
    """align source and target text into a table

    Args:
        source_text (str): reference text
        target_text (str): second text to align with
        columns (tuple[str, str]): names of columns on output

    Returns:
        pd.DataFrame: alignment table
    """
    source_tokens = [t.strip() for t in tokenize(source_text)]
    target_tokens = [t.strip() for t in tokenize(target_text)]

    mapping = pd.DataFrame(columns=("source", "target"))

    seqmatcher = SequenceMatcher(None, source_tokens, target_tokens)
    matches = seqmatcher.get_matching_blocks()

    # FIXME: patch to misaligned headers
    if not target_text:
        mapping["source"] = source_tokens
        mapping.fillna("", inplace=True)
    else:
        for match, next_match in zip(matches, matches[1:]):
            _aux = {
                "source": source_tokens[match.a : match.a + match.size],
                "target": target_tokens[match.b : match.b + match.size],
            }
            mapping = pd.concat([mapping, pd.DataFrame(_aux)], ignore_index=True)

            # get how differ the tokens at the end of the current match to the next
            diff = Differ().compare(
                source_tokens[match.a + match.size : next_match.a],
                target_tokens[match.b + match.size : next_match.b],
            )
            diff = list(diff)
            left = [t[2:].strip() for t in diff if t.startswith(("-", " "))]
            right = [t[2:].strip() for t in diff if t.startswith("+")]
            right_agg = "/".join(right)

            _aux = pd.DataFrame({"source": left})
            _aux["target"] = right_agg

            mapping = pd.concat([mapping, pd.DataFrame(_aux)], ignore_index=True)

    # rename columns
    mapping.columns = columns

    return mapping.reset_index(drop=True)


def align_docs(
    source_path: str | Path,
    target_path: str | Path,
    columns: tuple[str, str] = ("source", "target"),
    source_preprocess: Callable[[str], str] | None = None,
    target_preprocess: Callable[[str], str] | None = None,
):
    """align two documents word to word

    Args:
        source_path (str | Path): source document path (reference)
        target_path (str | Path): target document path (target)

    Returns:
        pd.DataFrame: alignment table
    """
    source: str = extract_document(source_path, errors="raise")  # type: ignore
    target: str = extract_document(target_path, errors="raise")  # type: ignore

    # FIXME: Patch to fix anonymization format. not generalizable
    if source_preprocess:
        source = source_preprocess(source)
    if target_preprocess:
        target = target_preprocess(target)

    assert isinstance(source, str), f"invalid read of file `{source}`"
    assert isinstance(target, str), f"invalid read of file `{target}`"

    source_lines = list(map(str.strip, source.splitlines()))
    target_lines = list(map(str.strip, target.splitlines()))

    mapping = pd.DataFrame()

    # we look for the first alignment line to split the process
    # from top and down.
    seqmatcher = SequenceMatcher(None, source_lines, target_lines)
    matches = seqmatcher.get_matching_blocks()

    offset_lines = matches[0]

    source_offset = "\n".join(source_lines[: offset_lines.a])
    source_offset = len(source_offset)

    target_offset = "\n".join(target_lines[: offset_lines.b])
    target_offset = len(target_offset)

    top_mapping = align_text(
        source[:source_offset],
        target[:target_offset],
        columns=columns,
    )

    bottom_mapping = align_text(
        source[source_offset:],
        target[target_offset:],
        columns=columns,
    )

    mapping = pd.concat([mapping, top_mapping], ignore_index=True)
    mapping = pd.concat([mapping, bottom_mapping], ignore_index=True)

    return mapping


def add_empty_lines_between_paragraphs(
    reference: str,
    mapping: pd.DataFrame,
) -> pd.DataFrame:
    mapping = mapping.copy()
    reference = re.sub(r"\n+", "\n", reference)
    splitted = reference.splitlines()
    n_tokens = [len(line.split()) for line in splitted if line.split()]
    idx = [idx + i for i, idx in enumerate(np.cumsum(n_tokens))]

    for i in idx:
        try:
            mapping = pd.DataFrame(
                np.insert(
                    mapping.values,
                    i,
                    values=[""] * len(mapping.columns),
                    axis=0,
                ),
                columns=mapping.columns,
            )
        except Exception:
            pass

    return mapping
