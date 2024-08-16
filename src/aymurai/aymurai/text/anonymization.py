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

    def unzip_document(self, doc_path: str, output_dir: str) -> None:
        """
        Unzips the document file to the specified output directory.

        Args:
            doc_path (str): The path to the document file.
            output_dir (str): The directory where the contents of the document
                file will be extracted.
        """
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Open the doc file as a zip file
        with zipfile.ZipFile(doc_path, "r") as doc_zip:
            # Extract all the contents to the output directory
            doc_zip.extractall(output_dir)
            logger.info(f"unzipped {doc_path} to {output_dir}")

    def index_paragraphs(self, file: str) -> list[dict]:
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

    def match_paragraphs_with_predictions(
        self,
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

    def unify_consecutive_labels(
        self, sample: dict, text_key: str = "document"
    ) -> list[dict]:
        """
        Unifies consecutive labels in a sample.

        Args:
            sample (dict): A dictionary representing the sample.
            text_key (str, optional): The key for the text in the sample dictionary.
                Defaults to "document".

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

    def replace_labels_in_text(self, pred: dict, text_key: str = "document") -> str:
        """
        Replaces labels in the text with anonymized tokens.

        Args:
            pred (dict): A dictionary representing the prediction.
            text_key (str, optional): The key for the text in the prediction dictionary.
                Defaults to "document".

        Returns:
            str: The text with replaced labels.
        """
        pred = deepcopy(pred)
        doc = pred[text_key]

        # Unify consecutive labels
        unified_labels = self.unify_consecutive_labels(pred, text_key)

        # Initialize the offset
        offset = 0

        # Replace labels in the text
        for unified_label in unified_labels:
            # Adjust start and end character indices of the label
            start_char = unified_label["start_char"] + offset
            end_char = unified_label["end_char"] + offset
            len_text_to_replace = end_char - start_char

            # Replace the text with the anonymized token
            aymurai_label = xml.sax.saxutils.escape(
                f" <{unified_label['aymurai_label']}>"
            )
            len_aymurai_label = len(aymurai_label)

            doc = doc[:start_char] + aymurai_label + doc[end_char:]

            # Update the offset
            offset += len_aymurai_label - len_text_to_replace

        return re.sub(r" +", " ", doc).strip()

    def erase_duplicates_justseen(self, series: pd.Series) -> pd.Series:
        """
        Erases duplicates that were just seen between two consecutive rows.

        Args:
            series (pd.Series): The pandas Series to be processed.

        Returns:
            pd.Series: The processed pandas Series.
        """
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

    def parse_token_indices(self, sample: dict) -> pd.DataFrame:
        """
        Parses the token indices from a sample.

        Args:
            sample (dict): A dictionary representing the sample.

        Returns:
            pd.DataFrame: A pandas DataFrame representing the parsed token indices.
        """
        original_text = " ".join(
            [fragment["text"] for fragment in sample["metadata"]["fragments"]]
        )
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
                left, right = (splits[: counter[token]], splits[counter[token] :])
                left = "".join(left)
                right = "".join(right)

                start = sample["metadata"]["start"] + fragment["start"] + len(left)
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

    def normalize_document(self, xml_content: str) -> str:
        """
        Normalizes the XML document by removing extra spaces
            and preserving line breaks.

        Args:
            xml_content (str): The XML content to be normalized.

        Returns:
            str: The normalized XML content.
        """
        # Parse the XML content with lxml
        parser = etree.XMLParser(ns_clean=True)
        root = etree.fromstring(xml_content.encode("utf-8"), parser)

        # Extract namespaces
        namespaces = {k: v for k, v in root.nsmap.items() if k}

        # Process each paragraph
        for wp in root.xpath("//w:p", namespaces=namespaces):
            first = True

            # Find all w:r elements containing w:t elements
            for wr in wp.xpath(".//w:r", namespaces=namespaces):
                wt = wr.find(".//w:t", namespaces)
                if wt is not None and wt.text:
                    # Normalize spaces within the text, preserving new line breaks
                    wt.text = re.sub(r"[^\S\r\n]+", " ", wt.text)

                    # Add a leading space if not the first fragment in the paragraph
                    if not first:
                        wt.text = " " + wt.text.lstrip()
                    else:
                        wt.text = wt.text.lstrip()
                        first = False

                    # Remove trailing spaces from all fragments
                    wt.text = wt.text.rstrip()

                    # Set the xml:space attribute to preserve
                    wt.set(
                        "{http://www.w3.org/XML/1998/namespace}space",
                        "preserve",
                    )

                    # Check if the text is empty after normalization
                    if not wt.text or wt.text.strip() == "":
                        # Remove the w:r element from its parent
                        wr.getparent().remove(wr)

        # Write back the XML content to a string
        xml_str = etree.tostring(root, encoding="unicode", pretty_print=True)

        return xml_str

    def replace_text_in_xml(self, paragraphs: list[dict], base_dir: str) -> None:
        """
        Replaces text in XML files based on the provided paragraphs
            and saves the modified files.

        Args:
            paragraphs (list[dict]): A list of dictionaries representing
                the paragraphs to be replaced.
            base_dir (str): The base directory where the XML files are located.
        """
        tokens = pd.concat(
            [self.parse_token_indices(sample) for sample in paragraphs],
            ignore_index=True,
        )

        fragments = (
            tokens.groupby(["xml_file", "paragraph_index", "fragment_index"])
            .agg({"target": " ".join, "start_char": "min", "end_char": "max"})
            .reset_index()
        )

        for xml_file, group in fragments.groupby("xml_file"):
            group = group.sort_values("end_char", ascending=False)

            with open(f"{base_dir}/word/{xml_file}", "r+") as file:
                content = file.read()

                for _, r in group.iterrows():
                    start_char = r["start_char"]
                    end_char = r["end_char"]

                    target = r["target"]
                    target = re.sub(r"[^\S\r\n]+", " ", target)

                    content = content[:start_char] + target + content[end_char:]

                # MUST be at the end to dont screw up the indexes
                content = self.normalize_document(content)

                file.seek(0)
                file.write(content)
                file.truncate()

    def add_files_to_zip(self, zip_file: zipfile.ZipFile, directory: str) -> None:
        """
        Adds all files in the specified directory to a zip file.

        Args:
            zip_file (zipfile.ZipFile): The zip file to add the files to.
            directory (str): The directory containing the files to be added.
        """
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                zip_file.write(file_path, os.path.relpath(file_path, directory))

    def create_docx(self, xml_directory, output_file) -> None:
        """
        Creates a new DOCX file by adding XML components from the specified directory.

        Args:
            xml_directory (str): The directory containing the XML components.
            output_file (str): The path to the output DOCX file.
        """
        # Create a new zip file
        with zipfile.ZipFile(output_file, "w") as docx:
            # Add XML components
            self.add_files_to_zip(docx, xml_directory)

    def __call__(self, item: dict, preds: list[dict], output_dir: str = ".") -> None:
        """
        Performs the anonymization process on a document.

        Args:
            item (dict): The document item to be anonymized.
            preds (list[dict]): The list of predictions for the document.
            output_dir (str, optional): The directory to save the anonymized document.
                Defaults to ".".

        Raises:
            ValueError: If the document has an extension other than `.docx`.
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
