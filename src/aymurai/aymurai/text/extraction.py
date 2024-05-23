import os
import re
import logging
import zipfile
import tempfile
import unicodedata
from glob import glob
from pathlib import Path
from zipfile import BadZipFile
import xml.etree.ElementTree as ET

import magic
import textract
import xmltodict
from more_itertools import flatten
from textract.exceptions import ShellError
from textract.parsers import _get_available_extensions

from aymurai.logging import get_logger
from aymurai.meta.pipeline_interfaces import Transform
from aymurai.models.flair.utils import FlairTextNormalize
from aymurai.utils.misc import get_element, get_recursively
from aymurai.utils.cache import cache_load, cache_save, get_cache_key

logger = get_logger(__file__)

TEXTRACT_EXTENSIONS = _get_available_extensions()
MIMETYPE_EXTENSION_MAPPER = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/pdf": "pdf",
}


ERRORS = ["ignore", "coerce", "raise"]


REGEX_PARAGRAPH = r"((?<!\/)w:p\b)(?P<paragraph>.*?)(\/w:p\b)"
REGEX_FRAGMENT = r"(?<!\/)w:t\b.*?>(?P<text>.*?)(<.*?\/w:t)"


class InvalidFile(Exception):
    """Invalid File"""

    pass


class FulltextExtract(Transform):
    """
    Extract plain text from document files (doc, docx, odt)
    """

    def __init__(self, use_cache: bool = False, **kwargs):
        self.use_cache = use_cache
        self.kwargs = kwargs

    def __call__(self, item: dict) -> dict:
        """
        Extract plain text from document files (doc, docx, odt)

        Args:
            item (dict): data item

        Returns:
            dict: data item with extracted text
        """

        if not item.get("data"):
            item["data"] = {}

        cache_key = get_cache_key(item["path"], self.__name__)
        if self.use_cache and (cache_data := cache_load(key=cache_key)):
            # text = cache_data
            paragraphs = cache_data
        else:
            # text = extract_document(item["path"], **self.kwargs) or ""
            # Unzip document into a temporary directory
            with tempfile.TemporaryDirectory() as tempdir:
                unzip_document(item["path"], tempdir)
                xml_files = glob(f"{tempdir}/**/*.xml", recursive=True)
                paragraphs = (index_paragraphs(file) for file in xml_files)
                paragraphs = list(flatten(paragraphs))

                sorted_rels = get_sorted_document_rels(tempdir)
                sorted_paragraphs = sorted(
                    paragraphs,
                    key=lambda x: sorted_rels.get(
                        get_element(x, ["metadata", "xml_file"])
                    ),
                )

        if self.use_cache:
            # cache_save(text, key=cache_key)  # type: ignore
            cache_save(sorted_paragraphs, key=cache_key)

        # item["data"]["doc.text"] = text
        # item["data"]["doc.valid"] = bool(len(text))

        return sorted_paragraphs  # item


def get_extension(path: str) -> str:
    mimetype = magic.from_file(path, mime=True)
    return MIMETYPE_EXTENSION_MAPPER.get(mimetype, mimetype)


def _load_xml_from_odt(path: str, xmlfile: str = "styles.xml") -> str:
    """load xml file inside an odt

    Args:
        path (str): path to odt file
        xmlfile (str, optional): xml to open. Defaults to 'styles.xml'.

    Returns:
        str: xml content
    """
    with zipfile.ZipFile(path, "r") as odt:
        if xmlfile not in odt.namelist():
            return ""
        with odt.open(xmlfile) as file:
            content = file.read().decode("utf-8")

    return content


def get_header(path: str) -> list[str]:
    """Extract header from styles.xml inside a ODT file

    Args:
        path (str): path to odt file

    Returns:
        list[str]: header lines
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


def extract_document(
    filename: str | Path,
    errors: str = "ignore",
    **kwargs,
) -> str | None:
    """extract text from document by path

    Args:
        filename (str): document path
        errors (str, optional): {'ignore', 'raise', 'coerce'}, default 'ignore'
        - If :const:`'raise'`, then invalid parsing will raise an exception.
        - If :const:`'coerce'`, then invalid parsing will be setas :const:`NaN`
            and warn.
        - If :const:`'ignore'`, then invalid parsing will be set as :const:`NaN`
            but not warn.
        **kwargs: keyword arguments for textract.

    Raises:
        ValueError: Invalid argument
        InvalidFile: Invalid or unsupported file

    Returns:
        str: extracted document text
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
        logger.warn(f"skipping (invalid): {filename}")
        return

    try:
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

    docu = unicodedata.normalize("NFKC", docu)
    return docu


# Function to unzip the document file
def unzip_document(doc_path: str, output_dir: str) -> dict:
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Open the doc file as a zip file
    with zipfile.ZipFile(doc_path, "r") as doc_zip:
        # Extract all the contents to the output directory
        doc_zip.extractall(output_dir)
        logger.info(f"unzipped {doc_path} to {output_dir}")


def get_sorted_document_rels(base_dir: str) -> dict:
    rels_path = f"{base_dir}/word/_rels/document.xml.rels"
    with open(rels_path) as rels_file:
        rels_tree = ET.parse(rels_file)
        rels_root = rels_tree.getroot()

    # Extract the relationships and determine order
    namespaces = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}

    rels = {
        rel.attrib["Target"]: int(re.search(r"\d+", rel.attrib["Id"]).group())
        for rel in rels_root.findall("r:Relationship", namespaces)
    }

    headers = [key for key in rels.keys() if "header" in key]

    # Manually add document.xml key
    rels["document.xml"] = 0 if not headers else rels.get(headers[-1]) + 1

    # Increase the other positions if necessary
    document_xml_id = rels["document.xml"]
    if document_xml_id > 0:
        for k, v in rels.items():
            if v >= document_xml_id and k != "document.xml":
                rels[k] = v + 1

    # Sort relationships
    sorted_rels = dict(sorted(rels.items(), key=lambda item: item[1]))

    return sorted_rels


# Function to index paragraphs of XML file
def index_paragraphs(file):
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
        plain_text = "".join([fragment["normalized_text"] for fragment in fragments])

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
