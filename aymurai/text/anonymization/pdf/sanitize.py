from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pymupdf

from aymurai.logger import get_logger
from aymurai.settings import settings

logger = get_logger(__name__)


def _pdf_metadata_mod_date() -> str:
    """
    Builds the PDF metadata modification timestamp in UTC.

    Returns:
        str: The PDF-formatted UTC modification timestamp.
    """
    timestamp = datetime.now(timezone.utc)
    return timestamp.strftime("D:%Y%m%d%H%M%S+00'00'")


def _append_cleanup_rect(
    cleanup_rects: dict[int, list[pymupdf.Rect]],
    page_idx: int,
    rect: pymupdf.Rect | tuple[float, float, float, float] | None,
) -> None:
    """
    Appends a cleanup rectangle for later document sanitization.

    Args:
        cleanup_rects (dict[int, list[pymupdf.Rect]]): The cleanup rectangles grouped by page index.
        page_idx (int): The page index associated with the operation.
        rect (pymupdf.Rect | tuple[float, float, float, float] | None): The rectangle used by the helper.
    """
    if rect is None:
        return

    cleanup_rect = pymupdf.Rect(rect)
    if cleanup_rect.get_area() <= 0:
        return
    cleanup_rects.setdefault(page_idx, []).append(cleanup_rect)


def _cleanup_rect_for_page_op(op: dict[str, Any]) -> pymupdf.Rect | None:
    """
    Builds the cleanup rectangle for a standard page operation.

    Args:
        op (dict[str, Any]): The operation dictionary being processed.

    Returns:
        pymupdf.Rect | None: The cleanup rectangle for the page operation, if available.
    """
    if op.get("image_rect") is not None:
        cleanup_rect = pymupdf.Rect(op["image_rect"])
        redact_rect = op.get("redact_rect")
        if redact_rect is not None:
            cleanup_rect.include_rect(pymupdf.Rect(redact_rect))
        return cleanup_rect

    cleanup_source = (
        op.get("redact_rect") or op.get("background_rect") or op.get("canvas_rect")
    )
    if cleanup_source is None:
        return None
    return pymupdf.Rect(cleanup_source)


def _cleanup_rect_for_widget_op(op: dict[str, Any]) -> pymupdf.Rect | None:
    """
    Builds the cleanup rectangle for a text widget operation.

    Args:
        op (dict[str, Any]): The operation dictionary being processed.

    Returns:
        pymupdf.Rect | None: The cleanup rectangle for the widget operation, if available.
    """
    widget_info = op.get("widget_info") or {}
    widget_rect = widget_info.get("rect")
    if widget_rect is None:
        return None
    return pymupdf.Rect(widget_rect)


def _cleanup_rect_for_signature_widget_op(op: dict[str, Any]) -> pymupdf.Rect | None:
    """
    Builds the cleanup rectangle for a signature widget operation.

    Args:
        op (dict[str, Any]): The operation dictionary being processed.

    Returns:
        pymupdf.Rect | None: The cleanup rectangle for the signature widget operation, if available.
    """
    widget_rect = op.get("widget_rect")
    if widget_rect is not None:
        return pymupdf.Rect(widget_rect)

    background_rect = op.get("background_rect") or op.get("canvas_rect")
    if background_rect is None:
        return None
    return pymupdf.Rect(background_rect)


def _collect_link_cleanup_rects(
    page_ops: dict[int, list[dict]],
    widget_ops: dict[int, list[dict]],
    signature_widget_ops: dict[int, list[dict]],
) -> dict[int, list[pymupdf.Rect]]:
    """
    Collects cleanup rectangles used to prune overlapping links.

    Args:
        page_ops (dict[int, list[dict]]): The collected page operations grouped by page index.
        widget_ops (dict[int, list[dict]]): The collected text widget operations grouped by page index.
        signature_widget_ops (dict[int, list[dict]]): The collected signature widget operations grouped by page index.

    Returns:
        dict[int, list[pymupdf.Rect]]: The cleanup rectangles grouped by page index.
    """
    cleanup_rects: dict[int, list[pymupdf.Rect]] = {}

    for page_idx, ops in page_ops.items():
        for op in ops:
            _append_cleanup_rect(cleanup_rects, page_idx, _cleanup_rect_for_page_op(op))

    for page_idx, ops in widget_ops.items():
        for op in ops:
            _append_cleanup_rect(
                cleanup_rects,
                page_idx,
                _cleanup_rect_for_widget_op(op),
            )

    for page_idx, ops in signature_widget_ops.items():
        for op in ops:
            _append_cleanup_rect(
                cleanup_rects,
                page_idx,
                _cleanup_rect_for_signature_widget_op(op),
            )

    return cleanup_rects


def _remove_overlapping_page_links(
    doc: pymupdf.Document,
    cleanup_rects: dict[int, list[pymupdf.Rect]],
) -> None:
    """
    Deletes page links that overlap anonymized regions.

    Args:
        doc (pymupdf.Document): The PDF document being processed.
        cleanup_rects (dict[int, list[pymupdf.Rect]]): The cleanup rectangles grouped by page index.
    """
    for page_idx, page_rects in cleanup_rects.items():
        if not page_rects:
            continue

        page = doc[page_idx]
        for link in list(page.get_links()):
            link_rect = link.get("from")
            if link_rect is None:
                continue
            link_rect = pymupdf.Rect(link_rect)
            if not any(link_rect.intersects(rect) for rect in page_rects):
                continue
            try:
                page.delete_link(link)
            except Exception as exc:
                logger.warning(
                    "Failed to delete PDF link on page=%s rect=%s: %s",
                    page_idx,
                    tuple(round(value, 2) for value in link_rect),
                    exc,
                )


def _remove_remaining_annotations(doc: pymupdf.Document) -> None:
    """
    Deletes residual page annotations after sanitization.

    Args:
        doc (pymupdf.Document): The PDF document being processed.
    """
    for page_idx, page in enumerate(doc):
        for annot in list(page.annots() or []):
            try:
                page.delete_annot(annot)
            except Exception as exc:
                logger.warning(
                    "Failed to delete residual PDF annotation on page=%s: %s",
                    page_idx,
                    exc,
                )


def _clear_standard_metadata(doc: pymupdf.Document) -> None:
    """
    Clears the standard PDF metadata fields on a document.

    Args:
        doc (pymupdf.Document): The PDF document being processed.
    """
    doc.set_metadata(
        {
            "title": "",
            "author": "",
            "subject": "",
            "keywords": "",
            "creator": "",
            "producer": "",
            "creationDate": "",
            "modDate": "",
            "trapped": "",
        }
    )


def _apply_aymurai_metadata(doc: pymupdf.Document) -> None:
    """
    Applies the configured AymurAI tooling metadata fields to the PDF document.

    Args:
        doc (pymupdf.Document): The PDF document being processed.
    """
    metadata = dict(doc.metadata or {})
    metadata.update(
        {
            "title": metadata.get("title") or "",
            "author": "",
            "subject": metadata.get("subject") or "",
            "keywords": metadata.get("keywords") or "",
            "creator": settings.ANONYMIZATION_METADATA_CREATOR,
            "producer": settings.ANONYMIZATION_METADATA_PRODUCER,
            "creationDate": metadata.get("creationDate") or "",
            "modDate": _pdf_metadata_mod_date(),
            "trapped": metadata.get("trapped") or "",
        }
    )
    doc.set_metadata(metadata)


def _sanitize_document(
    doc: pymupdf.Document,
    cleanup_rects: dict[int, list[pymupdf.Rect]],
) -> None:
    """
    Sanitizes document-level PDF metadata, attachments, and annotations.

    Args:
        doc (pymupdf.Document): The PDF document being processed.
        cleanup_rects (dict[int, list[pymupdf.Rect]]): The cleanup rectangles grouped by page index.
    """
    _remove_overlapping_page_links(doc, cleanup_rects)
    doc.scrub(
        metadata=True,
        xml_metadata=True,
        javascript=True,
        attached_files=True,
        embedded_files=True,
        thumbnails=True,
        reset_responses=True,
        hidden_text=True,
        clean_pages=True,
        remove_links=False,
        reset_fields=False,
        redactions=False,
    )
    _remove_remaining_annotations(doc)
    _clear_standard_metadata(doc)
    _apply_aymurai_metadata(doc)

    get_xml_metadata = getattr(doc, "get_xml_metadata", None)
    del_xml_metadata = getattr(doc, "del_xml_metadata", None)
    if callable(get_xml_metadata) and callable(del_xml_metadata):
        try:
            xml_metadata = get_xml_metadata()
        except Exception as exc:
            logger.warning("Failed to read PDF XML metadata after scrub: %s", exc)
        else:
            if xml_metadata:
                try:
                    del_xml_metadata()
                except Exception as exc:
                    logger.warning(
                        "Failed to delete residual PDF XML metadata: %s",
                        exc,
                    )
