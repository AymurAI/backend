import logging
import mimetypes
import os
import unicodedata
import zipfile
from functools import cache
from pathlib import Path
from typing import Any
from zipfile import BadZipFile

import markdown2
import textract
import xmltodict
from bs4 import BeautifulSoup
from lxml import etree
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.renderers.markdown import MarkdownRenderer
from marker.schema import BlockTypes
from more_itertools import flatten
from textract.exceptions import ShellError
from textract.parsers import _get_available_extensions

from aymurai.logger import get_logger
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


MARKER_PDF_CONFIG = {
    "layout_batch_size": 8,
    "detection_batch_size": 8,
    "table_rec_batch_size": 8,
    "recognition_batch_size": 8,
    "ocr_error_batch_size": 8,
    "force_ocr": True,
    "strip_existing_ocr": True,
}

INCLUDE_BLOCKS = {
    BlockTypes.PageHeader,
    BlockTypes.PageFooter,
    BlockTypes.SectionHeader,
    BlockTypes.Text,
    BlockTypes.Table,
    BlockTypes.Figure,
    BlockTypes.Picture,
    BlockTypes.Footnote,
    BlockTypes.ListGroup,
    BlockTypes.Code,
}

BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre"}


class InvalidFile(Exception):
    """Invalid File"""

    pass


def _zip_contains(path: str, member: str) -> bool:
    """
    Check if a zip file contains a specific member.

    Args:
        path (str): Path to the zip file.
        member (str): Member name to check for.

    Returns:
        bool: True if the member exists in the zip file, False otherwise.
    """
    try:
        with zipfile.ZipFile(path, "r") as archive:
            return member in archive.namelist()

    except (FileNotFoundError, PermissionError, OSError) as exc:
        logger.warning("Cannot access '%s': %s", path, exc)

    except BadZipFile as exc:
        logger.warning("Invalid zip structure for '%s': %s", path, exc)

    return False


def get_extension(path: str) -> str:
    # First, try by extension
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        try:
            with open(path, "rb") as file_handle:
                header = file_handle.read(1024)

        except (FileNotFoundError, PermissionError, OSError) as exc:
            logger.warning("Cannot open '%s': %s", path, exc)

        else:
            # PDF header check: scan for %PDF within the first 1KB
            if b"%PDF" in header:
                return "pdf"

    if ext == ".docx" and _zip_contains(path, "word/document.xml"):
        return "docx"

    if ext == ".odt" and _zip_contains(path, "content.xml"):
        return "odt"

    # Fallback to mimetypes
    mimetype, _ = mimetypes.guess_type(path)
    if mimetype in MIMETYPE_EXTENSION_MAPPER:
        return MIMETYPE_EXTENSION_MAPPER[mimetype]

    if ext:
        logger.debug("Falling back to raw extension for '%s'", path)
        return ext[1:]

    logger.warning("Unable to identify file type for '%s'", path)
    return "unknown"


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


def _build_marker_pdf_config() -> dict[str, int | str | bool]:
    """Return marker config patched with runtime device/env overrides."""
    config = MARKER_PDF_CONFIG.copy()

    # Configure TORCH_DEVICE if set (e.g., "cuda" or "cpu").
    torch_device = os.getenv("TORCH_DEVICE")
    if torch_device:
        config["TORCH_DEVICE"] = torch_device

    # Enable verbose marker traces when LOG_LEVEL is set to debug (matches logger pattern).
    log_level = os.getenv("LOG_LEVEL", "").lower()
    if log_level == "debug":
        config["debug"] = True

    return config


@cache
def _get_marker_pdf_converter_and_md_renderer() -> tuple[
    PdfConverter, MarkdownRenderer
]:
    """
    Return cached marker PDF converter and markdown renderer.

    Returns:
        tuple: (PdfConverter, MarkdownRenderer)
    """
    pdf_converter = PdfConverter(
        artifact_dict=create_model_dict(),
        config=_build_marker_pdf_config(),
    )

    markdown_renderer = MarkdownRenderer(
        {
            "keep_pageheader_in_output": True,
            "keep_pagefooter_in_output": True,
        }
    )

    return pdf_converter, markdown_renderer


def markdown_to_text(md: str) -> str:
    """
    Convert Markdown content to plain text by extracting relevant blocks.

    Args:
        md (str): Markdown content.

    Returns:
        str: Extracted plain text content.
    """
    html = markdown2.markdown(md, extras=["tables"])
    soup = BeautifulSoup(html, "html.parser")

    chunks = []
    for block in soup.find_all(BLOCK_TAGS):
        if block.find_parent(BLOCK_TAGS):
            continue
        chunks.append(block.get_text(" ", strip=True))

    return "\n\n".join(filter(None, chunks))


def pdf_to_text(file_path: str | Path) -> str:
    """
    Extract text from a PDF file using marker-pdf and return plain text.

    Args:
        file_path (str | Path): Path to the PDF file.

    Raises:
        InvalidFile: If the file does not exist.

    Returns:
        str: Extracted plain text content.
    """
    # Ensure file exists
    filepath = Path(file_path)
    if not filepath.exists():
        raise InvalidFile(f"Invalid path: {filepath}")

    logger.info(f"Extracting text from PDF: {filepath}")

    # Get marker converter and build document
    pdf_converter, markdown_renderer = _get_marker_pdf_converter_and_md_renderer()
    document = pdf_converter.build_document(filepath=filepath.as_posix())

    # Render the document in Markdown format
    markdown_output = markdown_renderer(document)

    # Convert Markdown to plain text
    plain_text = markdown_to_text(markdown_output.markdown)
    return unicodedata.normalize("NFKC", plain_text)


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

    ext = get_extension(filename)

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
        logger.warning(f"Skipping (invalid): {filename}")
        return

    try:
        if ext == "pdf":
            return pdf_to_text(filename)

        docu = textract.process(filename, **kwargs).decode("utf-8")
    except (BadZipFile, KeyError, ShellError, ImportError) as exc:
        if errors == "raise":
            raise
        logger.warning(f"Skipping (corrupted): {filename} ({exc})")
        return
    except Exception as exc:
        if errors == "raise":
            raise
        logger.warning(f"Skipping (corrupted): {filename} ({exc})")
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
