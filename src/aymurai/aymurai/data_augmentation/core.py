import re
from itertools import groupby

from joblib import hash
from more_itertools import unzip, flatten


class DataAugmentator:
    def __init__(self, augmentation_functions: dict, code2label: dict) -> None:
        self.augmentation_functions = augmentation_functions
        self.code2label = code2label
        self.label2code = {v: k for k, v in self.code2label.items()}

    def get_tokens_and_labels(self, text: str, entity: str) -> tuple[list, list]:
        tokens = text.split()
        tags = [f"I-{entity}"] * len(tokens)
        tags[0] = f"B-{entity}"
        return tokens, tags

    def augment(self, sample: dict) -> tuple[list, list]:
        sample_tokens = sample["tokens"]
        sample_tags = sample["tags"]
        sample_labels = [
            re.sub(r"^[BI]-", "", self.code2label.get(tag)) for tag in sample_tags
        ]

        augmented_tokens = []
        augmented_labels = []

        for entity, group in groupby(
            zip(sample_tokens, sample_labels), key=lambda x: x[1]
        ):
            tokens, labels = unzip(group)

            if entity == "O":
                augmented_tokens.append(list(tokens))
                augmented_labels.append(list(labels))
                continue

            replacement_tokens, replacement_labels = self.get_tokens_and_labels(
                self.augmentation_functions.get(entity)(), entity
            )

            augmented_tokens.append(list(replacement_tokens))
            augmented_labels.append(list(replacement_labels))

        augmented_tokens = list(flatten(augmented_tokens))
        augmented_labels = list(flatten(augmented_labels))
        augmented_tags = [self.label2code.get(label) for label in augmented_labels]
        n_labels = len([tag for tag in augmented_tags if tag > 0])

        augmented_sample = {
            "n_labels": n_labels,
            "tokens": augmented_tokens,
            "tags": augmented_tags,
            "hash": hash(" ".join(augmented_tokens)),
        }

        return augmented_sample
