import os
import tempfile
from glob import glob

from more_itertools import flatten

from aymurai.database.meta.extra import ParagraphPredictionPublic
from aymurai.logger import get_logger
from aymurai.text.anonymization.alignment import (
    index_paragraphs,
    match_paragraphs_with_predictions,
)
from aymurai.text.anonymization.xml_docx import (
    create_docx,
    replace_text_in_xml,
    unzip_document,
)

logger = get_logger(__file__)


def anonymize_docx(
    path: str,
    paragraph_preds: list[ParagraphPredictionPublic],
    output_dir: str = ".",
) -> None:
    """
    Performs the anonymization process on a document.

    Args:
        path (str): The path to the document to be anonymized.
        paragraph_preds (list[ParagraphPredictionPublic]): The list of predictions for the document.
        output_dir (str, optional): The directory to save the anonymized document.
            Defaults to ".".

    Raises:
        ValueError: If the document has an extension other than `.docx`.
    """
    if not os.path.splitext(path)[-1] == ".docx":
        raise ValueError("Only `.docx` extension is allowed.")

    if not os.path.exists(path):
        raise ValueError(f"File not found: {path}")

    # Unzip document into a temporary directory
    with tempfile.TemporaryDirectory() as tempdir:
        unzip_document(path, tempdir)

        # Parse XML files
        xml_files = glob(f"{tempdir}/**/*.xml", recursive=True)
        source_paragraphs = (index_paragraphs(file) for file in xml_files)
        source_paragraphs = list(flatten(source_paragraphs))

        # Filter out empty paragraphs
        source_paragraphs = [p for p in source_paragraphs if p.plain_text.strip()]

        # Matching
        paragraphs = match_paragraphs_with_predictions(
            source_paragraphs, paragraph_preds
        )

        # Edit XML files
        replace_text_in_xml(paragraphs, tempdir)

        # Recreate anonymized document
        os.makedirs(output_dir, exist_ok=True)
        create_docx(
            tempdir,
            f"{output_dir}/{os.path.basename(path)}",
        )
