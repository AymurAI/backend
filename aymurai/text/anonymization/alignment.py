import os
import re
from copy import deepcopy
from unicodedata import normalize

import numpy as np
import pandas as pd
from jiwer import cer
from joblib import hash
from more_itertools import flatten

from aymurai.models.flair.utils import FlairTextNormalize
from aymurai.utils.alignment.core import align_text, tokenize

REGEX_PARAGRAPH = r"((?<!\/)w:p\b)(?P<paragraph>.*?)(\/w:p\b)"
REGEX_FRAGMENT = r"(?<!\/)w:t\b.*?>(?P<text>.*?)(<.*?\/w:t)"


def resolve_render_token(label: dict, render_context: dict | None = None) -> str:
    """
    Resolves the render token for a label using the current render context.

    Args:
        label (dict): Label dictionary with attrs.

    Returns:
        str: Render token to insert in the document.
    """
    if not render_context:
        return label["attrs"]["aymurai_label"]

    policy = render_context["policy"]
    count_by_base = render_context["count_by_base"]
    index_by_entity = render_context["index_by_entity"]

    attrs = label.get("attrs") or {}
    base = attrs.get("aymurai_label")

    subclasses = attrs.get("aymurai_label_subclass") or []
    if policy.use_subclass_when_available and subclasses:
        base = subclasses[0].upper()

    if not base:
        base = label.get("label") or label.get("text") or "ENT"

    entity_id = attrs.get("canonical_entity_id") or label.get("text")
    key = (base, str(entity_id))
    index = index_by_entity.get(key)

    if policy.suffix_mode == "never" or index is None:
        return base

    if policy.suffix_mode == "auto":
        if count_by_base.get(base, 0) <= policy.suffix_threshold:
            return base

    return f"{base}_{index}"


def unify_consecutive_labels(
    sample: dict,
    text_key: str = "document",
    render_context: dict | None = None,
) -> list[dict]:
    """
    Unifies consecutive labels in a sample.

    Args:
        sample (dict): A dictionary representing the sample.
        text_key (str, optional): The key for the text in the sample dictionary.
            Defaults to "document".
        render_context (dict | None, optional): The context for rendering labels. Defaults to None.

    Returns:
        list[dict]: A list of dictionaries representing the unified labels.
    """
    sample = deepcopy(sample)

    # Extract labels and document text
    labels = sample["labels"]
    document = sample[text_key]

    # Reorder labels based on start indices
    labels = sorted(labels, key=lambda x: x["start_char"])

    unified_labels = []
    current_group = None

    # Iterate over labels
    for label in labels:
        # Get attributes
        text = label["attrs"]["aymurai_alt_text"] or label["text"]
        start_char = label["attrs"]["aymurai_alt_start_char"] or label["start_char"]
        end_char = label["attrs"]["aymurai_alt_end_char"] or label["end_char"]
        aymurai_label = resolve_render_token(label, render_context)

        if current_group is None:
            # Start a new group with the current label
            current_group = {
                "text": text,
                "start_char": start_char,
                "end_char": end_char,
                "aymurai_label": aymurai_label,
            }
        elif (
            current_group["aymurai_label"] == aymurai_label
            and (start_char - current_group["end_char"]) <= 1
        ):
            # Extend the current group with the current label
            current_group["end_char"] = end_char
        else:
            # Finish the current group and start a new one
            current_group["text"] = document[
                current_group["start_char"] : current_group["end_char"] + 1
            ]
            unified_labels.append(current_group)
            current_group = {
                "text": text,
                "start_char": start_char,
                "end_char": end_char,
                "aymurai_label": aymurai_label,
            }

    # Finish the last group
    if current_group is not None:
        current_group["text"] = document[
            current_group["start_char"] : current_group["end_char"] + 1
        ]
        unified_labels.append(current_group)

    return unified_labels


def replace_labels_in_text(
    pred: dict,
    text_key: str = "document",
    render_context: dict | None = None,
) -> str:
    """
    Replaces labels in the text with anonymized tokens.

    Args:
        pred (dict): A dictionary representing the prediction.
        text_key (str, optional): The key for the text in the prediction dictionary.
            Defaults to "document".
        render_context (dict | None, optional): The context for rendering labels. Defaults to None.
    Returns:
        str: The text with replaced labels.
    """
    pred = deepcopy(pred)
    doc = pred[text_key]

    # Unify consecutive labels
    unified_labels = unify_consecutive_labels(
        pred, render_context=render_context, text_key=text_key
    )

    # Initialize the offset
    offset = 0

    # Replace labels in the text
    for unified_label in unified_labels:
        # Adjust start and end character indices of the label
        start_char = unified_label["start_char"] + offset
        end_char = unified_label["end_char"] + offset
        len_text_to_replace = end_char - start_char

        # Replace the text with the anonymized token
        aymurai_label = f" <{unified_label['aymurai_label']}>"
        len_aymurai_label = len(aymurai_label)

        doc = doc[:start_char] + aymurai_label + doc[end_char:]

        # Update the offset
        offset += len_aymurai_label - len_text_to_replace

    return re.sub(r" +", " ", doc).strip()


def erase_duplicates_justseen(series: pd.Series) -> pd.Series:
    """
    Replaces consecutive duplicate values in a pandas Series with an empty string, keeping only the first occurrence.

    Args:
        series (pd.Series): The input pandas Series.

    Returns:
        pd.Series: A pandas Series with consecutive duplicates replaced by an empty string.
    """
    return series.where(series.ne(series.shift(), fill_value=None), "")


def parse_token_indices(
    sample: dict, render_context: dict | None = None
) -> pd.DataFrame:
    """
    Parses the token indices from a sample.

    Args:
        sample (dict): A dictionary representing the sample.
        render_context (dict | None, optional): The context for rendering labels. Defaults to None.

    Returns:
        pd.DataFrame: A pandas DataFrame representing the parsed token indices.
    """
    original_text = " ".join(
        [fragment["text"] for fragment in sample["metadata"]["fragments"]]
    )
    anonymized_text = replace_labels_in_text(sample, render_context=render_context)

    aligned = align_text(
        "<START> " + original_text + " <END>",
        "<START> " + anonymized_text + " <END>",
    )
    aligned["target"] = erase_duplicates_justseen(aligned["target"])

    xml_file = sample["metadata"]["xml_file"]

    tokens = []
    for i, fragment in enumerate(sample["metadata"]["fragments"]):
        text = fragment["text"]
        tokenized_text = tokenize(text)
        paragraph_index = fragment["paragraph_index"]

        # Use re.finditer to locate each instance of tokens in the text
        token_matches = list(
            re.finditer(r"\S+", text)
        )  # \S+ matches any non-whitespace sequence

        # Loop over tokenized text and token_matches in parallel
        for j, (token, match) in enumerate(zip(tokenized_text, token_matches)):
            start = sample["metadata"]["start"] + fragment["start"] + match.start()
            end = start + len(token)

            tokens.append((xml_file, paragraph_index, i, j, token, start, end))

    tokens = pd.DataFrame(
        tokens,
        columns=[
            "xml_file",
            "paragraph_index",
            "fragment_index",
            "token_index",
            "token",
            "start_char",
            "end_char",
        ],
    )

    tokens = pd.concat(
        [tokens, aligned["target"].iloc[1:-1].reset_index(drop=True)], axis=1
    )

    tokens["target"] = tokens["target"].fillna("")

    return tokens


def index_paragraphs(file: str) -> list[dict]:
    """
    Indexes the paragraphs of an XML file.

    Args:
        file (str): The path to the XML file to be indexed.

    Returns:
        list[dict]: A list of dictionaries representing the indexed paragraphs.
    """
    # Read the XML file
    with open(file) as f:
        xml = f.read()

    paragraphs = []
    paragraph_index = 0

    # Find all paragraphs in the XML file
    for match in re.finditer(REGEX_PARAGRAPH, xml):
        paragraph = match.group("paragraph")
        paragraph_start = match.start("paragraph")
        paragraph_end = match.end("paragraph")
        fragments = []
        fragment_index = 0

        # Find all text fragments in the paragraph
        for fragment in re.finditer(REGEX_FRAGMENT, paragraph):
            text = fragment.group("text")
            start = fragment.start("text")
            end = fragment.end("text")

            fragment_dict = {
                "text": text,
                "normalized_text": FlairTextNormalize.normalize_text(text),
                "start": start,
                "end": end,
                "fragment_index": fragment_index,
                "paragraph_index": paragraph_index,
            }
            fragments.append(fragment_dict)
            fragment_index += 1

        # Join all fragments as plain text
        plain_text = "".join([fragment["normalized_text"] for fragment in fragments])

        paragraphs.append(
            {
                "plain_text": plain_text,
                "metadata": {
                    "start": paragraph_start,
                    "end": paragraph_end,
                    "fragments": fragments,
                    "xml_file": os.path.basename(file),
                },
            }
        )
        paragraph_index += 1

    return paragraphs


def match_paragraphs_with_predictions(
    paragraphs: list[dict],
    predictions: list[dict],
) -> list[dict]:
    """
    Matches each paragraph with its corresponding predictions.

    Args:
        paragraphs (list[dict]): A list of dictionaries representing the paragraphs.
        predictions (list[dict]): A list of dictionaries representing
            the predictions.

    Returns:
        list[dict]: A list of dictionaries representing
            the matched paragraphs with predictions.
    """

    paragraphs = deepcopy(paragraphs)

    # Hash prediction documents
    pred_hashes = [hash(prediction["document"]) for prediction in predictions]
    idx2hash = {i: _hash for i, _hash in enumerate(pred_hashes)}

    # Hash paragraphs
    paragraphs = [
        paragraph | {"hash": hash(normalize("NFKC", paragraph["plain_text"].strip()))}
        for paragraph in paragraphs
    ]

    # Assign prediction indices to each paragraph by hash
    hash2idx = {
        paragraph["hash"]: np.where(np.array(pred_hashes) == paragraph["hash"])[
            0
        ].tolist()
        for paragraph in paragraphs
    }

    paragraphs = [
        paragraph | {"pred_indices": hash2idx[paragraph["hash"]]}
        for paragraph in paragraphs
    ]

    # Identify missing indices
    missing_indices = list(set(idx2hash.keys()) - set(flatten(list(hash2idx.values()))))

    if missing_indices:
        # Assign prediction indices to each paragraph by lowest CER
        target_texts = np.array([prediction["document"] for prediction in predictions])[
            missing_indices
        ]

        missing_paragraphs = [
            paragraph for paragraph in paragraphs if not paragraph["pred_indices"]
        ]

        for missing_paragraph in missing_paragraphs:
            source_text = missing_paragraph["plain_text"]
            min_cer_idx = np.argmin(
                [cer(source_text, target_text) for target_text in target_texts]
            )
            missing_paragraph["pred_indices"] = [missing_indices[min_cer_idx]]

    # Assign document text and labels
    paragraphs = [
        paragraph
        | {
            "document": predictions[paragraph["pred_indices"][0]]["document"],
            "labels": predictions[paragraph["pred_indices"][0]]["labels"],
        }
        for paragraph in paragraphs
    ]

    return paragraphs
