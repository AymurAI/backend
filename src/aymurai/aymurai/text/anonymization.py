import os
import re
import zipfile
import tempfile
from glob import glob
import xml.sax.saxutils
from copy import deepcopy
from collections import Counter
from unicodedata import normalize

import numpy as np
import pandas as pd
from jiwer import cer
from lxml import etree
from more_itertools import flatten

from aymurai.logging import get_logger
from aymurai.meta.pipeline_interfaces import Transform
from aymurai.models.flair.utils import FlairTextNormalize
from aymurai.utils.alignment.core import tokenize, align_text
from aymurai.utils.cache import cache_load, cache_save, get_cache_key

logger = get_logger(__file__)


REGEX_PARAGRAPH = r"((?<!\/)w:p\b)(?P<paragraph>.*?)(\/w:p\b)"
REGEX_FRAGMENT = r"(?<!\/)w:t\b.*?>(?P<text>.*?)(<.*?\/w:t)"


class DocAnonymizer(Transform):
    """
    Anonymize document by replacing sensitive data with label tokens
    """

    def __init__(self, use_cache: bool = False, **kwargs):
        self.use_cache = use_cache
        self.kwargs = kwargs

    # Function to unzip the document file
    def unzip_document(self, doc_path: str, output_dir: str) -> dict:
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Open the doc file as a zip file
        with zipfile.ZipFile(doc_path, "r") as doc_zip:
            # Extract all the contents to the output directory
            doc_zip.extractall(output_dir)
            logger.info(f"unzipped {doc_path} to {output_dir}")

    # Function to index paragraphs of XML file
    def index_paragraphs(self, file):
        with open(file) as f:
            xml = f.read()

        paragraphs = []
        paragraph_index = 0

        for match in re.finditer(REGEX_PARAGRAPH, xml):
            paragraph = match.group("paragraph")
            paragraph_start = match.start("paragraph")
            paragraph_end = match.end("paragraph")
            fragments = []
            fragment_index = 0

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
            plain_text = "".join(
                [fragment["normalized_text"] for fragment in fragments]
            )

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

    # Functon to match each paragraph with corresponding predictions
    def match_paragraphs_with_predictions(
        self,
        paragraphs: list[dict],
        predictions: list[dict],
    ) -> list[dict]:
        paragraphs = deepcopy(paragraphs)

        # Hash prediction documents
        pred_hashes = [hash(prediction["document"]) for prediction in predictions]
        idx2hash = {i: _hash for i, _hash in enumerate(pred_hashes)}

        # Hash paragraphs
        paragraphs = [
            paragraph
            | {"hash": hash(normalize("NFKC", paragraph["plain_text"].strip()))}
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
        missing_indices = list(
            set(idx2hash.keys()) - set(flatten(list(hash2idx.values())))
        )

        if missing_indices:
            # Assign prediction indices to each paragraph by lowest CER
            target_texts = np.array(
                [prediction["document"] for prediction in predictions]
            )[missing_indices]

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

    # Function to unify same consecutive labels
    def unify_consecutive_labels(
        self, sample: dict, text_key: str = "document"
    ) -> list[dict]:
        labels = sample["labels"]
        document = sample[text_key]

        unified_labels = []
        current_group = None

        for label in labels:
            if current_group is None:
                # Start a new group with the current label
                current_group = {
                    "text": label["text"],
                    "start_char": label["start_char"],
                    "end_char": label["end_char"],
                    "aymurai_label": label["attrs"]["aymurai_label"],
                }
            elif (
                current_group["aymurai_label"] == label["attrs"]["aymurai_label"]
                and (label["start_char"] - current_group["end_char"]) <= 1
            ):
                # Extend the current group with the current label
                current_group["end_char"] = label["end_char"]
            else:
                # Finish the current group and start a new one
                current_group["text"] = document[
                    current_group["start_char"] : current_group["end_char"] + 1
                ]
                unified_labels.append(current_group)
                current_group = {
                    "text": label["text"],
                    "start_char": label["start_char"],
                    "end_char": label["end_char"],
                    "aymurai_label": label["attrs"]["aymurai_label"],
                }

        # Finish the last group
        if current_group is not None:
            current_group["text"] = document[
                current_group["start_char"] : current_group["end_char"] + 1
            ]
            unified_labels.append(current_group)

        return unified_labels

    # Function to replace labels in text
    def replace_labels_in_text(self, pred: dict, text_key: str = "document") -> str:
        pred = deepcopy(pred)
        doc = pred[text_key]

        unified_labels = self.unify_consecutive_labels(pred, text_key)
        offset = 0

        for unified_label in unified_labels:
            start_char = unified_label["start_char"] + offset
            end_char = unified_label["end_char"] + offset
            len_text_to_replace = end_char - start_char

            aymurai_label = xml.sax.saxutils.escape(
                f" <{unified_label['aymurai_label']}>"
            )
            len_aymurai_label = len(aymurai_label)

            doc = doc[:start_char] + aymurai_label + doc[end_char:]

            offset += len_aymurai_label - len_text_to_replace

        return re.sub(r" +", " ", doc).strip()

    # Function to erase duplicates justseen between two consecutive rows
    def erase_duplicates_justseen(self, series: pd.Series) -> pd.Series:
        return pd.Series(
            [
                (
                    ""
                    if (i > 0 and series.iloc[i] == series.iloc[i - 1])
                    else series.iloc[i]
                )
                for i in range(len(series))
            ]
        )

    # Function to parse token indices
    def parse_token_indices(self, sample: dict) -> pd.DataFrame:
        original_text = " ".join(
            [fragment["text"] for fragment in sample["metadata"]["fragments"]]
        )  # sample["plain_text"]
        anonymized_text = self.replace_labels_in_text(sample)

        aligned = align_text(
            "<START> " + original_text + " <END>",
            "<START> " + anonymized_text + " <END>",
        )
        aligned["target"] = self.erase_duplicates_justseen(aligned["target"])

        xml_file = sample["metadata"]["xml_file"]

        tokens = []
        for i, fragment in enumerate(sample["metadata"]["fragments"]):
            text = fragment["text"]
            tokenized_text = tokenize(text)
            paragraph_index = fragment["paragraph_index"]

            counter = Counter()
            for j, token in enumerate(tokenized_text):
                counter.update([token])

                splits = text.split(token)
                left, right = splits[: counter[token]], splits[counter[token] :]
                left = "".join(left)
                right = "".join(right)

                start = sample["metadata"]["start"] + fragment["start"] + len(left)
                end = start + len(token)

                fragment_start = sample["metadata"]["start"] + fragment["start"]
                fragment_end = sample["metadata"]["start"] + fragment["end"]

                tokens.append(
                    (
                        xml_file,
                        paragraph_index,
                        i,
                        j,
                        token,
                        start,
                        end,
                        fragment_start,
                        fragment_end,
                        text,
                    )
                )

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
                "original_start_char",
                "original_end_char",
                "original_text",
            ],
        )

        tokens = pd.concat(
            [tokens, aligned["target"].iloc[1:-1].reset_index(drop=True)], axis=1
        )

        tokens["target"] = tokens["target"].fillna("")

        return tokens

    # Look for every w:t tag in the document, attach the whitespace_preserve attribute,
    # replace multiple spaces with a single space, and remove empty blocks
    def normalize_document(
        self,
        xml_content: str,
    ) -> str:
        # Parse the XML content with lxml
        parser = etree.XMLParser(ns_clean=True)
        root = etree.fromstring(xml_content.encode("utf-8"), parser)

        # Extract namespaces
        namespaces = {k: v for k, v in root.nsmap.items() if k}

        # Find all w:r elements containing w:t elements
        for wr in root.xpath("//w:r", namespaces=namespaces):
            wt = wr.find(".//w:t", namespaces)
            if wt is not None:
                # Set the xml:space attribute to preserve
                wt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

                # Replace multiple spaces with a single space in the text content
                if wt.text:
                    wt.text = re.sub(r"\s+", " ", wt.text)

                # Check if the text is empty after normalization
                if not wt.text or wt.text.strip() == "":
                    # Remove the w:r element from its parent
                    wr.getparent().remove(wr)

        # Write back the XML content to a string
        xml_str = etree.tostring(root, encoding="unicode", pretty_print=True)

        return xml_str

    def replace_text_in_xml(self, paragraphs: list[dict], base_dir: str):
        tokens = pd.concat(
            [self.parse_token_indices(sample) for sample in paragraphs],
            ignore_index=True,
        )

        fragments = (
            tokens.groupby(["xml_file", "paragraph_index", "fragment_index"])
            .agg(
                {
                    "target": " ".join,
                    "start_char": "min",
                    "end_char": "max",
                    "original_start_char": "min",
                    "original_end_char": "max",
                    "original_text": "first",
                }
            )
            .reset_index()
        )

        for xml_file, group in fragments.groupby("xml_file"):
            group = group.sort_values("end_char", ascending=False)

            with open(f"{base_dir}/word/{xml_file}", "r+") as file:
                content = file.read()

                for i, r in group.iterrows():
                    start_char = r["original_start_char"]
                    end_char = r["original_end_char"]

                    target = r["target"]

                    text = r["original_text"]
                    if text.startswith(" ") and not target.startswith(" "):
                        target = " " + target
                    if text.endswith(" ") and not target.endswith(" "):
                        target = target + " "

                    target = re.sub(r"\s+", " ", target)

                    content = content[:start_char] + target + content[end_char:]

                # MUST be at the end to dont screw up the indexes
                content = self.normalize_document(content)

                file.seek(0)
                file.write(content)
                file.truncate()

    # Function to add files to a zip archive
    def add_files_to_zip(self, zip_file, directory):
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                zip_file.write(file_path, os.path.relpath(file_path, directory))

    # Function to create the DOCX file
    def create_docx(self, xml_directory, output_file):
        # Create a new zip file
        with zipfile.ZipFile(output_file, "w") as docx:
            # Add XML components
            self.add_files_to_zip(docx, xml_directory)

    def __call__(self, item: dict, preds: dict, output_dir: str = ".") -> None:
        """
        Anonymize document

        Args:
            item (dict): data item
            preds (dict):
        """
        item_path = item["path"]

        if not os.path.splitext(item_path)[-1] == ".docx":
            raise ValueError("Only `.docx` extension is allowed.")

        if not item.get("data"):
            item["data"] = {}

        cache_key = get_cache_key(item_path, self.__name__)
        if self.use_cache and (cache_data := cache_load(key=cache_key)):
            paragraphs = cache_data
        else:
            # Unzip document into a temporary directory
            with tempfile.TemporaryDirectory() as tempdir:
                self.unzip_document(item_path, tempdir)

                # Parse XML files
                xml_files = glob(f"{tempdir}/**/*.xml", recursive=True)
                paragraphs = (self.index_paragraphs(file) for file in xml_files)
                paragraphs = list(flatten(paragraphs))

                # Filter out empty paragraphs
                paragraphs = [
                    paragraph
                    for paragraph in paragraphs
                    if paragraph["plain_text"].strip()
                ]

                # Matching
                paragraphs = self.match_paragraphs_with_predictions(paragraphs, preds)

                # Edit XML filess
                self.replace_text_in_xml(paragraphs, tempdir)

                # Recreate anonymized document
                os.makedirs(output_dir, exist_ok=True)
                self.create_docx(
                    tempdir,
                    f"{output_dir}/{os.path.basename(item_path)}",
                )

        if self.use_cache:
            cache_save(paragraphs, key=cache_key)
