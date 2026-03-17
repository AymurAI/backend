import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import AbstractSet, Any

import pymupdf
import pymupdf.layout  # noqa: F401  # activates layout support
import pymupdf4llm
import xmltodict
from lxml import etree
from more_itertools import flatten

from aymurai.logger import get_logger
from aymurai.utils.misc import get_element, get_recursively

logger = get_logger(__file__)


ODT_NS = {"text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
PDF_SKIP_BOX_CLASSES = frozenset({"picture", "formula", "table"})


def normalize_text(text: str) -> str:
    """
    Normalize Unicode output consistently across extractors.

    Args:
        text (str): Raw text extracted from a document.

    Returns:
        str: Normalized string in NFKC form.
    """
    return unicodedata.normalize("NFKC", text)


def _clean_pdf_box_text(text: str, box_class: str) -> str:
    """
    Clean box-level PDF text while preserving the original layout content.

    Args:
        text (str): Raw text sliced from a page box.
        box_class (str): Box class emitted by ``pymupdf4llm``.

    Returns:
        str: Cleaned, normalized box text.
    """
    text = normalize_text(text).strip()
    if box_class == "footnote":
        text = re.sub(r"(?m)^>\s?", "", text)
    return text


def pdf_to_paragraphs(
    file_path: Path | str,
    *,
    include_headers: bool = True,
    include_footers: bool = True,
    skip_box_classes: AbstractSet[str] = PDF_SKIP_BOX_CLASSES,
) -> list[str]:
    """
    Extract paragraph-like layout units from a PDF using PyMuPDF layout parsing.

    Args:
        file_path (Path | str): Path to the PDF document.
        include_headers (bool): Whether to keep header boxes.
        include_footers (bool): Whether to keep footer boxes.
        skip_box_classes (AbstractSet[str]): Layout box classes to ignore.

    Returns:
        list[str]: Normalized paragraph strings extracted from the PDF.
    """
    logger.debug("Extracting layout paragraphs from PDF: %s", file_path)

    with pymupdf.open(str(file_path)) as doc:
        parsed_doc = pymupdf4llm.parse_document(
            doc,
            filename=str(file_path),
            show_progress=False,
            force_text=True,
            use_ocr=False,
            force_ocr=False,
        )

        chunks = parsed_doc.to_text(
            page_chunks=True,
            header=include_headers,
            footer=include_footers,
            show_progress=False,
        )

    paragraphs: list[str] = []
    for chunk in chunks:
        page_text = chunk.get("text") or ""
        for box in chunk.get("page_boxes") or []:
            if box.get("class") in skip_box_classes:
                continue

            start, stop = box.get("pos", (0, 0))
            text = _clean_pdf_box_text(page_text[start:stop], box.get("class") or "")
            if text:
                paragraphs.append(text)

    return paragraphs


def pdf_to_text(file_path: Path | str) -> str:
    """
    Extract normalized plain text from a PDF using filtered layout boxes.

    Args:
        file_path (Path | str): Path to the PDF document.

    Returns:
        str: Cleaned textual content extracted from the PDF.
    """
    return "\n\n".join(pdf_to_paragraphs(file_path))


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
