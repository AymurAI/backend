import os
import re
from typing import Any

import numpy as np
import pandas as pd
from unidecode import unidecode


def normalize(text: str) -> str:
    """
    Normalize text by removing accents and non-word characters.

    Args:
        text (str): Input text.

    Returns:
        str: Normalized text.
    """
    text = unidecode(text)
    text = re.sub(r"\W", "", text)
    return text


def norm_ia2_label(text: Any, labels: list[str]) -> str | float:
    """
    Extract a single matching IA2 label from text.

    Args:
        text (Any): Input text containing IA2 label content.
        labels (list[str]): Valid label patterns to match.

    Returns:
        str | float: The matched label when unique, otherwise `np.nan`.
    """
    if not isinstance(text, str):
        return np.nan

    text = normalize(text)

    pattern = "|".join(labels)

    valid_labels = re.findall(pattern, text)
    valid_labels = list(set(valid_labels))

    return valid_labels[0] if len(valid_labels) == 1 else np.nan


def label_to_conll_format(labels: pd.Series) -> pd.Series:
    """
    Convert label sequences to CONLL BIO tags.

    Args:
        labels (pd.Series): Sequence of labels.

    Returns:
        pd.Series: Labels converted to BIO format.
    """
    labels = labels.copy()

    if len(labels.dropna()) == 0:
        return labels

    # tag the labels
    labels = "B-" + labels
    mask = labels.values[1:] == labels.values[:-1]
    mask = np.insert(mask, 0, False)
    labels.loc[mask] = labels.loc[mask].str.replace("B-", "I-")
    labels.fillna("O", inplace=True)

    return labels


def ia2_text_preprocess(text: str) -> str:
    """
    Insert whitespace after IA2 XML-like tags when missing.

    Args:
        text (str): Input text.

    Returns:
        str: Preprocessed text.
    """
    text = re.sub(r"(<\w+>)(\S)", r"\g<1> \g<2>", text)
    return text


def mapping2conll(
    df: pd.DataFrame,
    filename: str,
    text_column: str = "original",
    label_column: str = "label",
) -> None:
    """
    Write token-label mappings to a CONLL-style file.

    Args:
        df (pd.DataFrame): DataFrame containing token and label columns.
        filename (str): Output file path.
        text_column (str, optional): Column name containing tokens.
            Defaults to "original".
        label_column (str, optional): Column name containing labels.
            Defaults to "label".
    """
    dir = os.path.dirname(filename)
    os.makedirs(dir, exist_ok=True)
    with open(filename, "w") as file:
        print("-DOCSTART- -X- O", file=file)
        for _, row in df.iterrows():
            text = row[text_column]
            label = row[label_column]
            print(f"{text} -X- _ {label}" if text != " " else "", file=file)
