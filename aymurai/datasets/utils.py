import os
from glob import iglob

import numpy as np
import pandas as pd
from datasets import Dataset
from more_itertools import unzip, split_at

from aymurai.logging import get_logger
from aymurai.text.extraction import extract_document

logger = get_logger(__file__)


def __load_doc(example: dict) -> dict:
    example["text"] = extract_document(example["path"])
    return example


def load_documents_from(path: str) -> Dataset:
    logger.warn("This function return a huggingface dataset and it will be deprecated.")
    files = iglob(f"{path}/**/*.*", recursive=True)
    files = filter(os.path.isfile, files)
    files = list(files)

    dataset = Dataset.from_dict({"path": files})
    dataset = dataset.map(__load_doc, desc="Loading documents")
    dataset = dataset.filter(lambda example: bool(example["text"]))

    logger.info(f"founded {len(dataset)} files")
    return dataset


def pandas_to_dataset(df: pd.DataFrame, label2code: dict[str, int]) -> Dataset:
    df = df.copy()

    df["tags"] = df["label"].map(lambda x: label2code.get(x, label2code["O"]))
    items = []
    indices, rows = unzip(df.iterrows())
    tuples = map(lambda row: (row["token"], row["tags"]), rows)
    tuples = split_at(tuples, lambda x: pd.isna(x[0]))

    for i, paragraph in enumerate(tuples):
        df = pd.DataFrame(paragraph)
        if not len(df):
            continue
        tokens = df[0].values
        labels = df[1].values.astype(int)
        n_labels = len(labels[labels > 0])

        if any(np.isnan(labels)):
            continue

        if len(tokens) != len(labels):
            print("mismatch size")
            continue

        items.append(
            {
                "n_labels": n_labels,
                "tokens": list(tokens),
                "tags": labels,
            }
        )

    return Dataset.from_list(items)


def dataset_to_pandas(dataset: Dataset, code2label: dict[int, str]) -> pd.DataFrame:
    paragraphs = pd.DataFrame()
    for row in dataset:
        aux = pd.DataFrame(
            {
                "token": row["tokens"],
                "label": [code2label.get(code, "O") for code in row["tags"]],
            }
        )
        last_idx = len(aux)
        aux.loc[last_idx] = np.nan

        paragraphs = pd.concat([paragraphs, aux], ignore_index=True)
    return paragraphs
