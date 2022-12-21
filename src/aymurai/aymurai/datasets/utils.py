import os
from glob import iglob

from datasets import Dataset

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
