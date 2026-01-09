import os
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from functools import cache
from pathlib import Path
from typing import Any

import markdown2
import xmltodict
from bs4 import BeautifulSoup
from lxml import etree
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.renderers.markdown import MarkdownRenderer
from more_itertools import flatten

from aymurai.logger import get_logger
from aymurai.utils.misc import get_element, get_recursively

logger = get_logger(__file__)


BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"}

MarkerPdfConfig = dict[str, int | str | bool]

ODT_NS = {"text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}


def normalize_text(text: str) -> str:
    """
    Normalize Unicode output consistently across extractors.

    Args:
        text (str): Raw text extracted from a document.

    Returns:
        str: Normalized string in NFKC form.
    """
    return unicodedata.normalize("NFKC", text)


def markdown_to_text(md: str) -> str:
    """
    Convert Markdown content to plain text by extracting relevant blocks.

    Args:
        md (str): Markdown content produced by the renderer.

    Returns:
        str: Plain text representation stripped of nested blocks.
    """
    html = markdown2.markdown(md, extras=["tables"])
    soup = BeautifulSoup(html, "html.parser")

    chunks: list[str] = []
    for block in soup.find_all(BLOCK_TAGS):
        if block.find_parent(BLOCK_TAGS):
            continue
        chunks.append(block.get_text(" ", strip=True))

    return "\n\n".join(filter(None, chunks))


def _build_marker_pdf_config(
    layout_batch_size: int = 8,
    detection_batch_size: int = 8,
    table_rec_batch_size: int = 8,
    recognition_batch_size: int = 8,
    ocr_error_batch_size: int = 8,
    force_ocr: bool = False,
    strip_existing_ocr: bool = True,
    torch_device: str | None = None,
    debug: bool | None = None,
) -> MarkerPdfConfig:
    """
    Build marker configuration factoring in environment overrides.

    Args:
        layout_batch_size (int): Batch size for layout model inference. Defaults to 8.
        detection_batch_size (int): Batch size for detection model inference. Defaults to 8.
        table_rec_batch_size (int): Batch size for table recognition. Defaults to 8.
        recognition_batch_size (int): Batch size for OCR recognition. Defaults to 8.
        ocr_error_batch_size (int): Batch size for OCR error correction. Defaults to 8.
        force_ocr (bool): Force OCR even if text is detected. Defaults to False.
        strip_existing_ocr (bool): Remove embedded OCR layers before re-OCR. Defaults to True.
        torch_device (str | None): Optional override for the torch device. Defaults to None.
        debug (bool | None): Optional override for marker debug mode. Defaults to None.

    Returns:
        dict[str, int | str | bool]: Effective configuration for marker-pdf.
    """
    config: MarkerPdfConfig = {
        "layout_batch_size": layout_batch_size,
        "detection_batch_size": detection_batch_size,
        "table_rec_batch_size": table_rec_batch_size,
        "recognition_batch_size": recognition_batch_size,
        "ocr_error_batch_size": ocr_error_batch_size,
        "force_ocr": force_ocr,
        "strip_existing_ocr": strip_existing_ocr,
    }

    if torch_device is None:
        torch_device = os.getenv("TORCH_DEVICE")
    if torch_device:
        config["TORCH_DEVICE"] = torch_device

    if debug is None:
        log_level = os.getenv("LOG_LEVEL", "").lower()
        debug = log_level == "debug"

    if debug:
        config["debug"] = True

    return config


@cache
def get_marker_pdf_converter_and_md_renderer(
    config_items: tuple[tuple[str, int | str | bool], ...],
) -> tuple[PdfConverter, MarkdownRenderer]:
    """
    Provide cached marker PDF converter and Markdown renderer instances.

    Args:
        config_items (tuple[tuple[str, int | str | bool], ...]): Sorted config items
            to build a stable cache key.

    Returns:
        tuple[PdfConverter, MarkdownRenderer]: Ready-to-use converter and renderer.
    """
    pdf_converter = PdfConverter(
        artifact_dict=create_model_dict(),
        config=dict(config_items),
    )

    markdown_renderer = MarkdownRenderer(
        {
            "keep_pageheader_in_output": True,
            "keep_pagefooter_in_output": True,
        }
    )

    return pdf_converter, markdown_renderer


def _marker_config_key(
    config: MarkerPdfConfig,
) -> tuple[tuple[str, int | str | bool], ...]:
    return tuple(sorted(config.items()))


def pdf_to_text(
    file_path: Path,
    *,
    layout_batch_size: int = 8,
    detection_batch_size: int = 8,
    table_rec_batch_size: int = 8,
    recognition_batch_size: int = 8,
    ocr_error_batch_size: int = 8,
    force_ocr: bool = False,
    strip_existing_ocr: bool = True,
    torch_device: str | None = None,
    debug: bool | None = None,
) -> str:
    """
    Extract text from a PDF file and return normalized plain text.

    Args:
        file_path (Path): Path to the PDF document.
        layout_batch_size (int): Batch size for layout model inference. Defaults to 8.
        detection_batch_size (int): Batch size for detection model inference. Defaults to 8.
        table_rec_batch_size (int): Batch size for table recognition. Defaults to 8.
        recognition_batch_size (int): Batch size for OCR recognition. Defaults to 8.
        ocr_error_batch_size (int): Batch size for OCR error correction. Defaults to 8.
        force_ocr (bool): Force OCR even if text is detected. Defaults to False.
        strip_existing_ocr (bool): Remove embedded OCR layers before re-OCR. Defaults to True.
        torch_device (str | None): Optional override for the torch device. Defaults to None.
        debug (bool | None): Optional override for marker debug mode. Defaults to None.

    Returns:
        str: Cleaned textual content extracted from the PDF.
    """
    logger.info("Extracting text from PDF: %s", file_path)
    config = _build_marker_pdf_config(
        layout_batch_size=layout_batch_size,
        detection_batch_size=detection_batch_size,
        table_rec_batch_size=table_rec_batch_size,
        recognition_batch_size=recognition_batch_size,
        ocr_error_batch_size=ocr_error_batch_size,
        force_ocr=force_ocr,
        strip_existing_ocr=strip_existing_ocr,
        torch_device=torch_device,
        debug=debug,
    )
    pdf_converter, markdown_renderer = get_marker_pdf_converter_and_md_renderer(
        _marker_config_key(config)
    )
    document = pdf_converter.build_document(filepath=file_path.as_posix())
    markdown_output = markdown_renderer(document)
    plain_text = markdown_to_text(markdown_output.markdown)
    return normalize_text(plain_text)


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
