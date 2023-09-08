import re
from itertools import groupby

from joblib import hash
from more_itertools import unzip, flatten


class DataAugmenter:
    def __init__(self, augmentation_functions: dict, code2label: dict) -> None:
        self.augmentation_functions = augmentation_functions
        self.code2label = code2label
        self.label2code = {v: k for k, v in self.code2label.items()}

    def _get_tokens_and_tags(self, text: str, entity: str) -> tuple[list, list]:
        tokens = text.split()
        tags = [self.label2code.get(f"I-{entity}")] * len(tokens)
        tags[0] = self.label2code.get(f"B-{entity}")
        return tokens, tags

    def augment_sample(self, sample: dict) -> tuple[list, list]:
        sample_tokens = sample["tokens"]
        sample_tags = sample["tags"]
        sample_labels = [
            re.sub(r"^[BI]-", "", self.code2label.get(tag)) for tag in sample_tags
        ]

        augmented_tokens = []
        augmented_tags = []

        for entity, group in groupby(
            zip(sample_tokens, sample_tags, sample_labels), key=lambda x: x[2]
        ):
            tokens, tags, _ = unzip(group)

            if entity in ["O", "TEXTO_ANONIMIZAR"]:
                augmented_tokens.append(list(tokens))
                augmented_tags.append(list(tags))
                continue

            replacement_tokens, replacement_tags = self._get_tokens_and_tags(
                self.augmentation_functions.get(entity)(), entity
            )

            augmented_tokens.append(list(replacement_tokens))
            augmented_tags.append(list(replacement_tags))

        augmented_tokens = list(flatten(augmented_tokens))
        augmented_tags = list(flatten(augmented_tags))

        n_labels = len([tag for tag in augmented_tags if tag > 0])

        augmented_sample = {
            "n_labels": n_labels,
            "tokens": augmented_tokens,
            "tags": augmented_tags,
            "hash": hash(" ".join(augmented_tokens)),
        }

        return augmented_sample
