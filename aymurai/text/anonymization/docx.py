import os
import tempfile
from glob import glob
from pathlib import Path
from typing import Any

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
from aymurai.text.anonymization.watermarks import add_footer_watermark
from aymurai.text.anonymization.xml_docx import (
    create_docx,
    replace_text_in_xml,
    unzip_document,
)
from aymurai.utils.cache import cache_load, cache_save, get_cache_key


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

                # Add watermark to the footer
                add_footer_watermark(output_path)

        if self.use_cache:
            cache_save(paragraphs, key=cache_key)

        return f"{output_dir}/{os.path.basename(str(file_path))}"
