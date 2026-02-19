import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import xmltodict
from lxml import etree
from more_itertools import flatten

import pymupdf
import statistics
import numpy as np

from aymurai.logger import get_logger
from aymurai.utils.misc import get_element, get_recursively

logger = get_logger(__file__)


BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"}


ODT_NS = {"text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}


def _normalize_text(text: str) -> str:
    """
    Normalize Unicode output consistently across extractors.

    Args:
        text (str): Raw text extracted from a document.

    Returns:
        str: Normalized string in NFKC form.
    """
    return unicodedata.normalize("NFKC", text)


def _compute_median_margin_between_blocks(pdf_path: str) -> float:
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


def _extract_and_merge_paragraphs(pdf_path: str, y_tolerance=5) -> list[str]:
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


def pdf_to_text(
    file_path: Path | str,
    y_tolerance: float | None = None,
    debug: bool | None = None,
) -> str:
    """
    Extract text from a PDF file and return normalized plain text.

    Args:
        file_path (Path): Path to the PDF document.
        y_tolerance (float, optional):
            Maximum vertical gap (in points) to consider blocks part of the same paragraph.
        debug (bool | None): Optional override for marker debug mode. Defaults to None.

    Returns:
        str: Cleaned textual content extracted from the PDF.
    """
    logger.info("Extracting text from PDF: %s", file_path)

    if y_tolerance is None:
        y_tolerance = _compute_median_margin_between_blocks(file_path)

    paragraphs = _extract_and_merge_paragraphs(file_path, np.ceil(y_tolerance))
    docu = "\n\n".join(paragraphs)

    return _normalize_text(docu)


def load_xml_from_docx(path: Path, xmlfile: str = "word/footnotes.xml") -> Any | None:
    """
    Extract XML content from a specific file inside a DOCX container.

    Args:
        path (Path): DOCX archive path.
        xmlfile (str, optional): Internal member name to inspect. Defaults to "word/footnotes.xml".

    Returns:
        Any | None: Parsed XML tree or None when the member is missing.
    """
    with zipfile.ZipFile(path, "r") as docx:
        if xmlfile not in docx.namelist():
            return None
        with docx.open(xmlfile) as handle:
            return etree.parse(handle)


def load_xml_from_odt(path: Path, xmlfile: str = "styles.xml") -> str:
    """
    Load XML content from an ODT archive member.

    Args:
        path (Path): ODT archive path.
        xmlfile (str, optional): Member name to open. Defaults to "styles.xml".

    Returns:
        str: UTF-8 decoded XML content or an empty string when absent.
    """
    with zipfile.ZipFile(path, "r") as odt:
        if xmlfile not in odt.namelist():
            return ""
        with odt.open(xmlfile) as file:
            return file.read().decode("utf-8")


def get_header(path: Path) -> list[str]:
    """
    Extract header text defined in an ODT stylesheet.

    Args:
        path (Path): ODT document path.

    Returns:
        list[str]: Header snippets collected from the stylesheet.
    """
    styles_xml_content = load_xml_from_odt(path)
    if not styles_xml_content:
        return []

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

    return [text for text in texts if isinstance(text, str)]


def get_footnotes(path: Path) -> list[str] | None:
    """
    Extract footnotes from a DOCX document.

    Args:
        path (Path): DOCX document path.

    Returns:
        list[str] | None: Ordered footnote texts or None when absent.
    """
    footnotes_tree = load_xml_from_docx(path)
    if not footnotes_tree:
        return None

    footnotes_root = footnotes_tree.getroot()
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    footnotes_texts: list[str] = []
    for footnote in footnotes_root.findall("w:footnote", namespaces=ns):
        texts = footnote.xpath(".//w:t/text()", namespaces=ns)
        if texts:
            footnotes_texts.append("".join(texts))

    return footnotes_texts


def _odt_qn(name: str) -> str:
    """
    Resolve a qualified ODT tag into the ElementTree namespace form.

    Args:
        name (str): Namespaced tag in the ``prefix:local`` format.

    Returns:
        str: Expanded tag with namespace URI.
    """
    prefix, local = name.split(":", 1)
    return f"{{{ODT_NS[prefix]}}}{local}"


def _odt_text_to_string(elem) -> str:
    """
    Flatten an ODT Element into a plain-text string, preserving special tokens.

    Args:
        elem (Element): XML element to flatten.

    Returns:
        str: Concatenated text content for the element subtree.
    """
    out = elem.text or ""
    for child in elem:
        if child.tag == _odt_qn("text:tab"):
            out += "\t"
        elif child.tag == _odt_qn("text:s"):
            out += " " * int(child.get(_odt_qn("text:c"), 1))
        else:
            out += _odt_text_to_string(child)
        if child.tail:
            out += child.tail
    return out


def odt_to_text(path: Path) -> str:
    """
    Extract text content, preserving paragraphs and headings, from an ODT file.

    Args:
        path (Path): ODT document path.

    Returns:
        str: Plain text version of the document content.
    """
    with zipfile.ZipFile(path, "r") as archive:
        content_xml = archive.read("content.xml")

    content = ET.fromstring(content_xml)

    lines = []
    for child in content.iter():
        if child.tag in (_odt_qn("text:p"), _odt_qn("text:h")):
            lines.append(_odt_text_to_string(child))
    return "\n".join(lines)
