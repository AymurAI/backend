import os
import re
import xml.sax.saxutils
from copy import deepcopy
from unicodedata import normalize

import jiwer
import numpy as np
import pandas as pd
from more_itertools import flatten

from aymurai.database.meta.extra import ParagraphPredictionPublic
from aymurai.database.schema import PredictionPublic
from aymurai.meta.entities import DocLabel, EntityAttributes
from aymurai.meta.xml_document import (
    ParagraphMetadata,
    XMLParagraph,
    XMLParagraphWithParagraphPrediction,
    XMLTextFragment,
)
from aymurai.models.flair.utils import FlairTextNormalize
from aymurai.utils.alignment.core import align_text, tokenize

REGEX_PARAGRAPH = r"((?<!\/)w:p\b)(?P<paragraph>.*?)(\/w:p\b)"
REGEX_FRAGMENT = r"(?<!\/)w:t\b.*?>(?P<text>.*?)(<.*?\/w:t)"


def merge_consecutive_labels(text: str, labels: list[DocLabel]) -> list[DocLabel]:
    """
    Merge consecutive labels in the paragraph prediction.
    Args:
        text (str): The original text.
        labels (list[DocLabel]): A list of labels to merge.
    Returns:
        list[DocLabel]: A list of merged DocLabel objects.
    """
    if not labels:
        return []

    labels = sorted(labels, key=lambda x: x.start_char)
    merged = []
    current = labels[0]

    for label in labels[1:]:
        # Get label info
        cur_label = current.attrs.aymurai_label
        next_label = label.attrs.aymurai_label
        cur_end = current.attrs.aymurai_alt_end_char or current.end_char
        next_start = label.attrs.aymurai_alt_start_char or label.start_char
        # If same label and adjacent or overlapping
        if cur_label == next_label and (next_start - cur_end) <= 1:
            # Extend current label
            current = DocLabel(
                text=text[current.start_char : (label.end_char + 1)],
                start_char=current.start_char,
                end_char=label.end_char,
                attrs=EntityAttributes(
                    aymurai_label=cur_label,
                    aymurai_alt_text=text[current.start_char : (label.end_char + 1)],
                    aymurai_alt_start_char=current.start_char,
                    aymurai_alt_end_char=label.end_char,
                ),
            )
        else:
            merged.append(current)
            current = label
    merged.append(current)
    return merged


def replace_labels_in_text(text: str, prediction: PredictionPublic | None) -> str:
    """
    Replaces labels in the text with anonymized tokens.

    Args:
        text (str): The text to be anonymized.
        prediction (PredictionPublic): The prediction object containing labels.

    Returns:
        str: The text with replaced labels.
    """

    if not prediction:
        return text

    # merge consecutive labels
    # merged_labels = merge_consecutive_labels(text, prediction.labels)
    merged_labels = prediction.labels

    # Initialize the offset
    offset = 0

    # Replace labels in the text
    for label in merged_labels:
        # Adjust start and end character indices of the label
        start_char = label.start_char + offset
        end_char = label.end_char + offset
        len_text_to_replace = end_char - start_char

        # Replace the text with the anonymized token
        aymurai_label = xml.sax.saxutils.escape(f" <{label.attrs.aymurai_label}>")
        len_aymurai_label = len(aymurai_label)

        text = text[:start_char] + aymurai_label + text[end_char:]

        # Update the offset
        offset += len_aymurai_label - len_text_to_replace

    return re.sub(r" +", " ", text).strip()


def erase_duplicates_justseen(series: pd.Series) -> pd.Series:
    """
    Replaces consecutive duplicate values in a pandas Series with an empty string, keeping only the first occurrence.
    """
    return series.where(series.ne(series.shift(), fill_value=None), "")


def gen_alignment_table(paragraph: XMLParagraphWithParagraphPrediction) -> pd.DataFrame:
    original_text = " ".join([f.text for f in paragraph.metadata.fragments])
    anonymized_text = replace_labels_in_text(
        text=paragraph.plain_text,
        prediction=paragraph.paragraph_prediction.prediction,
    )

    aligned = align_text(
        "<START> " + original_text + " <END>",
        "<START> " + anonymized_text + " <END>",
    )
    aligned["target"] = erase_duplicates_justseen(aligned["target"])

    xml_file = paragraph.metadata.xml_file

    tokens = []
    for i, fragment in enumerate(paragraph.metadata.fragments):
        text = fragment.text
        tokenized_text = tokenize(text)
        paragraph_index = fragment.paragraph_index

        # Use re.finditer to locate each instance of tokens in the text
        # \S+ matches any non-whitespace sequence
        token_matches = list(re.finditer(r"\S+", text))

        # Loop over tokenized text and token_matches in parallel
        for j, (token, match) in enumerate(zip(tokenized_text, token_matches)):
            start = paragraph.metadata.start + fragment.start + match.start()
            end = start + len(token)

            # tokens.append((xml_file, paragraph_index, i, j, token, start, end))
            tokens.append(
                {
                    "xml_file": xml_file,
                    "paragraph_index": paragraph_index,
                    "fragment_index": i,
                    "token_index": j,
                    "token": token,
                    "start_char": start,
                    "end_char": end,
                }
            )

    tokens_df = pd.DataFrame(tokens)

    tokens_df = pd.concat(
        [
            tokens_df,
            aligned["target"].iloc[1:-1].reset_index(drop=True),
        ],
        axis=1,
    )

    tokens_df["target"].fillna("", inplace=True)

    return tokens_df


def index_paragraphs(file: str) -> list[XMLParagraph]:
    """
    Indexes the paragraphs of an XML file.

    Args:
        file (str): The path to the XML file to be indexed.

    Returns:
        list[Paragraph]: A list of Paragraph instances representing the indexed paragraphs.
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
        fragments: list[XMLTextFragment] = []
        fragment_index = 0

        # Find all text fragments in the paragraph
        for fragment in re.finditer(REGEX_FRAGMENT, paragraph):
            text = fragment.group("text")
            start = fragment.start("text")
            end = fragment.end("text")

            fragments.append(
                XMLTextFragment(
                    text=text,
                    normalized_text=FlairTextNormalize.normalize_text(text),
                    start=start,
                    end=end,
                    fragment_index=fragment_index,
                    paragraph_index=paragraph_index,
                )
            )
            fragment_index += 1

        # Join all fragments as plain text
        plain_text = "".join([fragment.normalized_text for fragment in fragments])

        paragraphs.append(
            XMLParagraph(
                plain_text=plain_text,
                metadata=ParagraphMetadata(
                    start=paragraph_start,
                    end=paragraph_end,
                    fragments=fragments,
                    xml_file=os.path.basename(file),
                ),
            )
        )
        paragraph_index += 1

    return paragraphs


def match_paragraphs_with_predictions(
    src_paragraphs: list[XMLParagraph],
    pred_paragraphs: list[ParagraphPredictionPublic],
) -> list[XMLParagraphWithParagraphPrediction]:
    """
    Matches each paragraph with its corresponding predictions.

    Args:
        paragraphs (list[dict]): A list of dictionaries representing the paragraphs.
        predictions (list[ParagraphPredictionPublic]): A list of ParagraphPredictionPublic
            instances representing the predictions.

    Returns:
        list[dict]: A list of dictionaries representing
            the matched paragraphs with predictions.
    """

    src_paragraphs = deepcopy(src_paragraphs)

    # Hash prediction documents
    def text_hash(text: str) -> int:
        return hash(normalize("NFKC", text.strip()))

    # Compute hashes for prediction paragraphs
    pred_hashes = [text_hash(pred.text) for pred in pred_paragraphs]
    idx2hash = {i: h for i, h in enumerate(pred_hashes)}

    # Compute hashes for source paragraphs
    for p in src_paragraphs:
        p.hash = text_hash(p.plain_text)

    # Map paragraph hashes to prediction indices
    hash2idx = {
        p.hash: [i for i, h in idx2hash.items() if h == p.hash] for p in src_paragraphs
    }

    # Assign prediction indices to each paragraph
    for p in src_paragraphs:
        p.__pred_indices = hash2idx[p.hash]

    # Find indices of predictions that have not been matched to any paragraph
    matched_indices = set(flatten(hash2idx.values()))
    all_indices = set(idx2hash.keys())
    missing_indices = list(all_indices - matched_indices)

    if missing_indices:
        # Assign prediction indices to each paragraph by lowest CER
        target_texts = np.array([pred.text for pred in pred_paragraphs])[
            missing_indices
        ]

        missing_paragraphs = [p for p in src_paragraphs if not p.__pred_indices]

        for missing_paragraph in missing_paragraphs:
            source_text = missing_paragraph.plain_text
            cer = np.array(
                [jiwer.cer(source_text, target_text) for target_text in target_texts]
            )
            min_cer_idx = np.argmin(cer)
            missing_paragraph.__pred_indices = [missing_indices[min_cer_idx]]

    # Assign document text and labels
    new_paragraphs = [
        XMLParagraphWithParagraphPrediction(
            **p.model_dump(),
            paragraph_prediction=pred_paragraphs[p.__pred_indices[0]],
        )
        for p in src_paragraphs
    ]

    return new_paragraphs
