import logging
import os
import statistics
import unicodedata
import zipfile
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import numpy as np
import pymupdf
import textract
import xmltodict
from lxml import etree
from more_itertools import flatten
from textract.exceptions import ShellError
from textract.parsers import _get_available_extensions

from aymurai.logger import get_logger
from aymurai.meta.pipeline_interfaces import Transform
from aymurai.utils.cache import cache_load, cache_save, get_cache_key
from aymurai.utils.misc import get_element, get_recursively

logger = get_logger(__file__)

TEXTRACT_EXTENSIONS = _get_available_extensions()
MIMETYPE_EXTENSION_MAPPER = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/pdf": "pdf",
}


ERRORS = ["ignore", "coerce", "raise"]


class InvalidFile(Exception):
    """Invalid File"""

    pass


class FulltextExtract(Transform):
    """
    Extract plain text from document files (doc, docx, odt, pdf).
    """

    def __init__(self, use_cache: bool = False, **kwargs):
        self.use_cache = use_cache
        self.kwargs = kwargs

    def __call__(self, item: dict) -> dict:
        """
        Extract plain text from document files (doc, docx, odt, pdf).

        Args:
            item (dict): data item.

        Returns:
            dict: data item with extracted text.
        """

        if not item.get("data"):
            item["data"] = {}

        cache_key = get_cache_key(item["path"], self.__name__)
        if self.use_cache and (cache_data := cache_load(key=cache_key)):
            text = cache_data
        else:
            text = extract_document(item["path"], **self.kwargs) or ""

        if self.use_cache:
            cache_save(text, key=cache_key)  # type: ignore

        item["data"]["doc.text"] = text
        item["data"]["doc.valid"] = bool(len(text))

        return item


def _load_xml_from_odt(path: str, xmlfile: str = "styles.xml") -> str:
    """
    Load xml file inside an odt.

    Args:
        path (str): path to odt file.
        xmlfile (str, optional): xml to open. Defaults to 'styles.xml'.

    Returns:
        str: xml content.
    """
    with zipfile.ZipFile(path, "r") as odt:
        if xmlfile not in odt.namelist():
            return ""
        with odt.open(xmlfile) as file:
            content = file.read().decode("utf-8")

    return content


def _load_xml_from_docx(path: str, xmlfile: str = "word/footnotes.xml") -> Any | None:
    """Extract XML content from a specific file inside a .docx."""
    with zipfile.ZipFile(path, "r") as docx:
        if xmlfile not in docx.namelist():
            return
        with docx.open(xmlfile) as f:
            return etree.parse(f)


def get_header(path: str) -> list[str]:
    """
    Extract header from styles.xml inside a ODT file.

    Args:
        path (str): path to odt file.

    Returns:
        list[str]: header lines.
    """
    styles_xml_content = _load_xml_from_odt(path)
    styles_dict = xmltodict.parse(styles_xml_content)

    header_root = get_element(
        styles_dict,
        levels=[
            "office:document-styles",
            "office:master-styles",
            "style:master-page",
        ],
    )

    if not isinstance(header_root, list):
        header_root = [header_root]

    style_header = [
        get_recursively(item, "style:header")
        for item in header_root
        if get_recursively(item, "style:header")
    ]
    style_header = list(flatten(style_header))

    texts = [
        get_recursively(item, "#text")
        for item in style_header
        if get_recursively(item, "#text")
    ]
    texts = list(flatten(texts))

    if not texts:
        return []

    return texts


def get_footnotes(path: str) -> list[str] | None:
    """
    Extract footnotes from footnotes.xml inside a DOCX file.

    Args:
        path (str): Path to the DOCX file.

    Returns:
        list[str]: Footnote texts.
    """
    footnotes_tree = _load_xml_from_docx(path)
    if not footnotes_tree:
        return

    footnotes_root = footnotes_tree.getroot()

    # Define the namespace map
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    # Extract footnote texts in order
    footnotes_texts = []
    for footnote in footnotes_root.findall("w:footnote", namespaces=ns):
        texts = footnote.xpath(".//w:t/text()", namespaces=ns)
        if texts:
            footnotes_texts.append("".join(texts))

    return footnotes_texts


def pdf_to_text(filename: str, y_tolerance: float | None = None) -> str:
    """
    Extract text from a PDF file.

    Args:
        filename (str): Path to the PDF file.
        y_tolerance (float, optional):
            Maximum vertical gap (in points) to consider blocks part of the same paragraph.

    Returns:
        str: Extracted text.
    """
    if y_tolerance is None:
        y_tolerance = compute_median_margin_between_blocks(filename)

    paragraphs = extract_and_merge_paragraphs(filename, np.ceil(y_tolerance))
    docu = "\n\n".join(paragraphs)
    docu = unicodedata.normalize("NFKC", docu)
    return docu


def extract_document(
    filename: str | Path,
    errors: str = "ignore",
    **kwargs,
) -> str | None:
    """
    Extract text from document by path.

    Args:
        filename (str): document path.
        errors (str, optional): {'ignore', 'raise', 'coerce'}, default 'ignore'
        - If :const:`'raise'`, then invalid parsing will raise an exception.
        - If :const:`'coerce'`, then invalid parsing will be setas :const:`NaN`
            and warn.
        - If :const:`'ignore'`, then invalid parsing will be set as :const:`NaN`
            but not warn.
        **kwargs: keyword arguments for textract.

    Raises:
        ValueError: Invalid argument.
        InvalidFile: Invalid or unsupported file.

    Returns:
        str: extracted document text.
    """
    filename = str(filename)  # patch for pathlib

    if errors not in ERRORS:
        raise ValueError(f"errors argument must be in {ERRORS}")

    _, ext = os.path.splitext(filename)
    ext = ext.lstrip(".").lower()

    kwargs["extension"] = kwargs.get("extension", ext)
    kwargs["output_encoding"] = kwargs.get("output_encoding", "utf-8")

    logger = get_logger(f"{__file__}.{__name__}")

    if errors == "ignore":
        logger.setLevel(logging.ERROR)

    if (
        not isinstance(filename, str)
        or not os.path.exists(filename)
        or ext not in TEXTRACT_EXTENSIONS
    ):
        if errors == "raise":
            raise InvalidFile(f"Invalid path: {filename}")
        logger.warn(f"skipping (invalid): {filename}")
        return

    try:
        if ext == "pdf":
            return pdf_to_text(filename, y_tolerance=kwargs.get("y_tolerance"))

        docu = textract.process(filename, **kwargs).decode("utf-8")
    except (BadZipFile, KeyError, ShellError):
        if errors == "raise":
            raise
        logger.warn(f"skipping (corrupted): {filename}")
        return

    # patch header loading in odt files
    if ext == "odt":
        header = "\n".join(get_header(filename))
        docu = header + "\n\n" + docu

    # patch footnotes loading in docx files
    if ext == "docx":
        footnotes = get_footnotes(filename) or []
        footnotes = "\n".join(footnotes)
        if footnotes.strip():
            docu = docu + "\n\n" + footnotes

    docu = unicodedata.normalize("NFKC", docu)
    return docu


def compute_median_margin_between_blocks(pdf_path: str) -> float:
    """
    Computes the median vertical margin between text blocks in a PDF.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        float: Median margin between text blocks (in points).
    """
    margins = []

    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            # Extract all text blocks from the page
            blocks = page.get_text("blocks")

            # Sort blocks by their top y-coordinate (y0)
            blocks_sorted = sorted(blocks, key=lambda b: b[1])

            # Compute vertical margins between consecutive blocks
            for i in range(1, len(blocks_sorted)):
                previous_block = blocks_sorted[i - 1]
                current_block = blocks_sorted[i]

                # Calculate the vertical margin
                previous_y1 = previous_block[3]  # Bottom of the previous block
                current_y0 = current_block[1]  # Top of the current block
                margin = current_y0 - previous_y1

                if margin > 0:  # Ignore overlapping blocks
                    margins.append(margin)

    # Compute and return the median margin
    if margins:
        return statistics.median(margins)
    else:
        return 0.0  # Return 0 if no margins were found


def extract_and_merge_paragraphs(pdf_path: str, y_tolerance=5) -> list[str]:
    """
    Extracts and merges paragraphs from a PDF by grouping close text blocks.

    Args:
        pdf_path (str): Path to the PDF file.
        y_tolerance (float): Maximum vertical gap (in points) to consider blocks part of the same paragraph.

    Returns:
        list[str]: A list of merged paragraphs as strings.
    """
    paragraphs = []
    current_paragraph = []
    last_y1 = None

    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            # Extract all text blocks from the page
            blocks = page.get_text("blocks")

            # Sort blocks by their top y-coordinate (y0)
            blocks_sorted = sorted(blocks, key=lambda b: b[1])

            for block in blocks_sorted:
                x0, y0, x1, y1, text, *_ = block

                if last_y1 is not None and (y0 - last_y1) > y_tolerance:
                    # If the gap between blocks is too large, start a new paragraph
                    if current_paragraph:
                        paragraphs.append(" ".join(current_paragraph))
                    current_paragraph = []

                current_paragraph.append(text)
                last_y1 = y1

            if current_paragraph:
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []

    return paragraphs
