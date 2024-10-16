import re

import numpy as np
import pandas as pd
from tqdm.auto import tqdm
from datasets import Dataset


def compute_label_counts(
    dataset: Dataset,
    code2label: dict[int, str],
) -> dict[str, int]:
    counts = []
    for example in tqdm(dataset, total=len(dataset)):
        labels = [code2label[code] for code in example["tags"]]
        labels = [re.sub(r"[BI]-", "", label) for label in labels]
        labels, count = np.unique(labels, return_counts=True)

        counts.append({l: c for l, c in zip(labels, count)})
    counts = pd.DataFrame(counts)
    counts = counts.sum().astype(int)
    return counts.to_dict()


def compute_label_weights(
    dataset: Dataset,
    code2label: dict[int, str],
    ignore_labels: list[str] = ["O", "PER", "FECHA"],
) -> dict[str, float]:
    counts = compute_label_counts(dataset, code2label)
    counts = pd.Series(counts)
    counts = counts.drop(ignore_labels)

    label_weights = counts.sum() / counts
    label_weights /= label_weights.min()
    label_weights = label_weights.to_dict()
    return label_weights
