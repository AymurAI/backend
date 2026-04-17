import os
import tempfile
from datetime import datetime, timezone
from glob import glob
from pathlib import Path
from typing import Any

from docx import Document
from more_itertools import flatten

from aymurai.text.anonymization.alignment import (
    index_paragraphs,
    match_paragraphs_with_predictions,
)
from aymurai.text.anonymization.base import (
    BaseAnonymizer,
    InvalidDocumentAnonymizer,
    register_anonymizer,
)
from aymurai.text.anonymization.docx.watermark import add_footer_watermark
from aymurai.settings import settings
from aymurai.text.anonymization.docx.xml import (
    create_docx,
    replace_text_in_xml,
    unzip_document,
)
from aymurai.utils.cache import cache_load, cache_save, get_cache_key


def _set_aymurai_core_properties(doc_path: str) -> None:
    """
    Applies the configured AymurAI tooling metadata fields to the DOCX core properties.

    Args:
        doc_path (str): The path to the DOCX document to update.
    """
    document = Document(doc_path)
    core_properties = document.core_properties
    core_properties.author = ""
    core_properties.last_modified_by = settings.ANONYMIZATION_METADATA_CREATOR
    core_properties.modified = datetime.now(timezone.utc)
    document.save(doc_path)


@register_anonymizer
class DocxAnonymizer(BaseAnonymizer):
    """
    Anonymize DOCX documents by replacing sensitive data with label tokens.
    """

    extension = "docx"

    def __init__(self, use_cache: bool = False):
        self.use_cache = use_cache

    def anonymize(
        self,
        item: dict,
        preds: list[dict],
        output_dir: str = ".",
        render_context: dict[str, Any] | None = None,
    ) -> str:
        """
        Anonymizes a DOCX document using the matched paragraph predictions.

        Args:
        item (dict): The item dictionary containing the input DOCX path.
        preds (list[dict]): The predictions to apply to the document.
        output_dir (str, optional): The directory where the anonymized document should be written. Defaults to '.'.
        render_context (dict[str, Any] | None, optional): The rendering context used to resolve replacement tokens.
            Defaults to None.

        Returns:
            str: The path to the anonymized DOCX output file.
        """
        item_path = Path(item["path"])
        file_path = self.ensure_file(item_path)

        if file_path.suffix.lower() != ".docx":
            raise InvalidDocumentAnonymizer("Only `.docx` extension is allowed.")

        if not item.get("data"):
            item["data"] = {}

        cache_key = get_cache_key(str(file_path), self.__name__)
        if self.use_cache and (cache_data := cache_load(key=cache_key)):
            paragraphs = cache_data
        else:
            # Unzip document into a temporary directory
            with tempfile.TemporaryDirectory() as tempdir:
                unzip_document(str(file_path), tempdir)

                # Parse XML files
                xml_files = glob(f"{tempdir}/**/*.xml", recursive=True)
                paragraphs = (index_paragraphs(file) for file in xml_files)
                paragraphs = list(flatten(paragraphs))

                # Filter out empty paragraphs
                paragraphs = [
                    paragraph
                    for paragraph in paragraphs
                    if paragraph["plain_text"].strip()
                ]
                # Matching
                paragraphs = match_paragraphs_with_predictions(paragraphs, preds)

                # Edit XML files
                replace_text_in_xml(paragraphs, tempdir, render_context)

                # Recreate anonymized document
                os.makedirs(output_dir, exist_ok=True)
                output_path = f"{output_dir}/{os.path.basename(str(file_path))}"
                create_docx(tempdir, output_path)

                # Add metadata branding and the footer watermark
                _set_aymurai_core_properties(output_path)
                add_footer_watermark(output_path)

        if self.use_cache:
            cache_save(paragraphs, key=cache_key)

        return f"{output_dir}/{os.path.basename(str(file_path))}"
