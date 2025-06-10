import os
import re

import numpy as np
import pandas as pd
from unidecode import unidecode


def normalize(text: str) -> str:
    text = unidecode(text)
    text = re.sub(r"\W", "", text)
    return text


def norm_ia2_label(text, labels: list[str]) -> str | float:
    if not isinstance(text, str):
        return np.nan

    text = normalize(text)

    pattern = "|".join(labels)

    valid_labels = re.findall(pattern, text)
    valid_labels = list(set(valid_labels))

    return valid_labels[0] if len(valid_labels) == 1 else np.nan


def label_to_conll_format(labels: pd.Series) -> pd.Series:
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
    text = re.sub(r"(<\w+>)(\S)", r"\g<1> \g<2>", text)
    return text


def mapping2conll(
    df: pd.DataFrame,
    filename: str,
    text_column: str = "original",
    label_column: str = "label",
):
    dir = os.path.dirname(filename)
    os.makedirs(dir, exist_ok=True)
    with open(filename, "w") as file:
        print("-DOCSTART- -X- O", file=file)
        for _, row in df.iterrows():
            text = row[text_column]
            label = row[label_column]
            print(f"{text} -X- _ {label}" if text != " " else "", file=file)
