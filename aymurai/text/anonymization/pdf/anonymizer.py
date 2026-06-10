from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pymupdf
import pymupdf.layout  # noqa: F401  # activates layout support
from pymupdf4llm.helpers import document_layout as pymupdf4llm_document_layout

from aymurai.text.anonymization.base import (
    BaseAnonymizer,
    InvalidDocumentAnonymizer,
    register_anonymizer,
)
from aymurai.text.anonymization.pdf.layout import (
    _apply_minimal_boundary_merge,
    _build_layout_paragraphs,
    _match_predictions_to_layout,
)
from aymurai.text.anonymization.pdf.ops import (
    _apply_redactions,
    _collect_page_redactions,
)
from aymurai.text.anonymization.pdf.sanitize import (
    _collect_link_cleanup_rects,
    _sanitize_document,
)
from aymurai.text.anonymization.pdf.watermark import add_pdf_footer_watermark


@register_anonymizer
class PdfAnonymizer(BaseAnonymizer):
    """
    Anonymize PDF documents by replacing sensitive data with label tokens.
    """

    extension = "pdf"

    def anonymize(
        self,
        item: dict,
        preds: list[dict],
        output_dir: str = ".",
        render_context: dict[str, Any] | None = None,
    ) -> str:
        """
        Anonymizes a PDF document using the matched paragraph predictions.

        Args:
            item (dict): The item dictionary containing the input PDF path.
            preds (list[dict]): The predictions to apply to the document.
            output_dir (str, optional): The directory where the anonymized document should be written. Defaults to '.'.
            render_context (dict[str, Any] | None, optional): The rendering context used to resolve replacement tokens. Defaults to None.

        Returns:
            str: The path to the anonymized PDF output file.
        """
        item_path = Path(item["path"])
        file_path = self.ensure_file(item_path)

        if file_path.suffix.lower() != ".pdf":
            raise InvalidDocumentAnonymizer("Only `.pdf` extension is allowed.")

        with pymupdf.open(str(file_path)) as doc:
            parsed_doc = pymupdf4llm_document_layout.parse_document(
                doc,
                filename=str(file_path),
                show_progress=False,
                force_text=True,
                use_ocr=False,
                force_ocr=False,
            )

            layout_paragraphs = _build_layout_paragraphs(parsed_doc)
            matched_paragraphs = _match_predictions_to_layout(
                layout_paragraphs,
                preds,
            )

            _apply_minimal_boundary_merge(matched_paragraphs, render_context)
            page_ops, widget_ops, signature_widget_ops = _collect_page_redactions(
                doc,
                matched_paragraphs,
                render_context,
            )
            _apply_redactions(doc, page_ops, widget_ops, signature_widget_ops)
            cleanup_rects = _collect_link_cleanup_rects(
                page_ops,
                widget_ops,
                signature_widget_ops,
            )
            _sanitize_document(doc, cleanup_rects)
            add_pdf_footer_watermark(doc)

            os.makedirs(output_dir, exist_ok=True)
            output_path = Path(output_dir) / f"{file_path.stem}.anonymized.pdf"
            doc.save(str(output_path), garbage=4, clean=1, deflate=1)

        return str(output_path)
