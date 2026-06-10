from aymurai.text.anonymization.alignment import replace_labels_in_text
from aymurai.text.anonymization.base import (
    BaseAnonymizer,
    InvalidDocumentAnonymizer,
    get_anonymizer,
    register_anonymizer,
    supported_extensions,
)
from aymurai.text.anonymization.docx import DocxAnonymizer
from aymurai.text.anonymization.pdf import PdfAnonymizer

__all__ = [
    "BaseAnonymizer",
    "DocxAnonymizer",
    "PdfAnonymizer",
    "InvalidDocumentAnonymizer",
    "get_anonymizer",
    "register_anonymizer",
    "supported_extensions",
    "replace_labels_in_text",
]
