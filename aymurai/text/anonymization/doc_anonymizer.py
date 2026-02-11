import os
import tempfile
from glob import glob

from more_itertools import flatten

from aymurai.meta.pipeline_interfaces import Transform
from aymurai.text.anonymization.alignment import (
    index_paragraphs,
    match_paragraphs_with_predictions,
)
from aymurai.text.anonymization.watermarks import add_footer_watermark
from aymurai.text.anonymization.xml_docx import (
    create_docx,
    replace_text_in_xml,
    unzip_document,
)
from aymurai.utils.cache import cache_load, cache_save, get_cache_key


class DocAnonymizer(Transform):
    """
    Anonymize document by replacing sensitive data with label tokens
    """

    def __init__(self, use_cache: bool = False):
        self.use_cache = use_cache
        self.render_context = None

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
                unzip_document(item_path, tempdir)

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

                # Edit XML filess
                replace_text_in_xml(paragraphs, tempdir, self.render_context)

                # Recreate anonymized document
                os.makedirs(output_dir, exist_ok=True)
                create_docx(
                    tempdir,
                    f"{output_dir}/{os.path.basename(item_path)}",
                )

                # Add watermark to the footer
                add_footer_watermark(f"{output_dir}/{os.path.basename(item_path)}")

        if self.use_cache:
            cache_save(paragraphs, key=cache_key)
