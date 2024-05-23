import os
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from glob import glob

from more_itertools import flatten

from aymurai.logging import get_logger
from aymurai.meta.pipeline_interfaces import Transform
from aymurai.models.flair.utils import FlairTextNormalize
from aymurai.utils.cache import cache_load, cache_save, get_cache_key
from aymurai.utils.misc import get_element

logger = get_logger(__file__)


REGEX_PARAGRAPH = r"((?<!\/)w:p\b)(?P<paragraph>.*?)(\/w:p\b)"
REGEX_FRAGMENT = r"(?<!\/)w:t\b.*?>(?P<text>.*?)(<.*?\/w:t)"


class DocxXMLExtract(Transform):
    """
    Extract plain text from document files (doc, docx, odt)
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

    def get_sorted_document_rels(self, base_dir: str) -> dict:
        rels_path = f"{base_dir}/word/_rels/document.xml.rels"
        with open(rels_path) as rels_file:
            rels_tree = ET.parse(rels_file)
            rels_root = rels_tree.getroot()

        # Extract the relationships and determine order
        namespaces = {
            "r": "http://schemas.openxmlformats.org/package/2006/relationships"
        }

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

    def __call__(self, item: dict) -> dict:
        """
        Extract plain text from document files (doc, docx, odt)

        Args:
            item (dict): data item

        Returns:
            dict: data item with extracted text
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
                xml_files = glob(f"{tempdir}/**/*.xml", recursive=True)
                paragraphs = (self.index_paragraphs(file) for file in xml_files)
                paragraphs = list(flatten(paragraphs))

                sorted_rels = self.get_sorted_document_rels(tempdir)
                sorted_paragraphs = sorted(
                    paragraphs,
                    key=lambda x: sorted_rels.get(
                        get_element(x, ["metadata", "xml_file"])
                    ),
                )

        if self.use_cache:
            cache_save(sorted_paragraphs, key=cache_key)

        return sorted_paragraphs
