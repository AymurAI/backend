from __future__ import annotations

from typing import Any

import pymupdf

from aymurai.logger import get_logger
from aymurai.text.anonymization.pdf.common import (
    _build_display_token_candidates,
    _default_style,
    _find_flexible,
    _get_base14_font,
)

logger = get_logger(__name__)


def _signature_background_rect(
    op: dict[str, Any],
    widget_rect: pymupdf.Rect,
) -> pymupdf.Rect:
    """
    Builds the background rectangle used for a signature replacement.

    Args:
        op (dict[str, Any]): The operation dictionary being processed.
        widget_rect (pymupdf.Rect): The rectangle occupied by the widget.

    Returns:
        pymupdf.Rect: The background rectangle for the signature replacement.
    """
    background = pymupdf.Rect(
        op.get("line_rect") or op.get("canvas_rect") or widget_rect
    )
    canvas_rect = op.get("canvas_rect")
    if canvas_rect is not None:
        background.include_rect(pymupdf.Rect(canvas_rect))

    pad_x = max(background.height * 0.75, 2.0)
    pad_y = max(background.height * 0.25, 0.75)
    widget_clip = pymupdf.Rect(widget_rect)

    background.x0 = max(widget_clip.x0, background.x0 - pad_x)
    background.y0 = max(widget_clip.y0, background.y0 - pad_y)
    background.x1 = min(widget_clip.x1, background.x1 + pad_x)
    background.y1 = min(widget_clip.y1, background.y1 + pad_y)
    return background


def _widget_text_color(widget: pymupdf.Widget) -> tuple[float, float, float]:
    """
    Extracts the text color configured on a PDF widget.

    Args:
        widget (pymupdf.Widget): The widget being processed.

    Returns:
        tuple[float, float, float]: The widget text color in PDF RGB components.
    """
    values = list(widget.text_color or [])
    if not values:
        return (0.0, 0.0, 0.0)
    if len(values) == 1:
        shade = float(values[0])
        return (shade, shade, shade)
    if len(values) >= 3:
        return tuple(float(value) for value in values[:3])
    return (0.0, 0.0, 0.0)


def _style_from_widget(widget: pymupdf.Widget) -> dict[str, Any]:
    """
    Builds a text style dictionary from a widget definition.

    Args:
        widget (pymupdf.Widget): The widget being processed.

    Returns:
        dict[str, Any]: The style dictionary derived from the widget.
    """
    return {
        "font": str(widget.text_font or ""),
        "flags": 0,
        "color": _widget_text_color(widget),
        "size": float(widget.text_fontsize or 10.0),
        "ascender": 0.8,
        "descender": -0.2,
    }


def _page_widget_infos(page: pymupdf.Page) -> list[dict[str, Any]]:
    """
    Collects text and signature widget metadata for a page.

    Args:
        page (pymupdf.Page): The PDF page being processed.

    Returns:
        list[dict[str, Any]]: The widget metadata collected for the page.
    """
    infos: list[dict[str, Any]] = []
    for widget in page.widgets() or []:
        if widget.field_type not in (
            pymupdf.PDF_WIDGET_TYPE_TEXT,
            pymupdf.PDF_WIDGET_TYPE_SIGNATURE,
        ):
            continue
        infos.append(
            {
                "xref": int(widget.xref),
                "field_type": int(widget.field_type),
                "field_name": str(widget.field_name or ""),
                "field_value": str(widget.field_value or ""),
                "rect": pymupdf.Rect(widget.rect),
                "style": _style_from_widget(widget),
            }
        )
    return infos


def _entity_overlaps_widget(
    entity_rect: pymupdf.Rect,
    widget_infos: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Finds the widget that most overlaps the given entity rectangle.

    Args:
        entity_rect (pymupdf.Rect): The rectangle representing the entity on the page.
        widget_infos (list[dict[str, Any]]): The widget metadata available for overlap checks.

    Returns:
        dict[str, Any] | None: The best overlapping widget info, if one exists.
    """
    best_widget: dict[str, Any] | None = None
    best_area = 0.0
    for widget_info in widget_infos:
        widget_rect = widget_info["rect"]
        if not entity_rect.intersects(widget_rect):
            continue
        area = (entity_rect & widget_rect).get_area()
        if area > best_area:
            best_area = area
            best_widget = widget_info
    return best_widget


def _fit_widget_token(
    widget_info: dict[str, Any],
    current_text: str,
    entity_span: tuple[int, int],
    token: str,
) -> str:
    """
    Finds a token variant that fits inside a widget value.

    Args:
        widget_info (dict[str, Any]): The widget metadata being processed.
        current_text (str): The current widget text value.
        entity_span (tuple[int, int]): The span of the entity inside the widget text.
        token (str): The logical replacement token being processed.

    Returns:
        str: The token variant that fits in the widget value.
    """
    style = widget_info.get("style") or _default_style()
    rect = pymupdf.Rect(widget_info["rect"])
    font_obj = _get_base14_font(style)
    max_width = max(rect.width - 1.0, 1.0)

    prefix = current_text[: entity_span[0]]
    suffix = current_text[entity_span[1] :]

    for candidate in _build_display_token_candidates(token):
        candidate_text = f"{prefix}{candidate}{suffix}"
        if (
            font_obj.text_length(
                candidate_text, fontsize=float(style.get("size") or 10.0)
            )
            <= max_width + 0.1
        ):
            return candidate

    candidates = _build_display_token_candidates(token)
    return candidates[0] if candidates else f"<{token}>"


def _apply_widget_ops(
    doc: pymupdf.Document,
    widget_ops: dict[int, list[dict]],
) -> None:
    """
    Applies collected replacements to editable text widgets.

    Args:
        doc (pymupdf.Document): The PDF document being processed.
        widget_ops (dict[int, list[dict]]): The collected text widget operations grouped by page index.
    """
    for page_idx, ops in widget_ops.items():
        if not ops:
            continue

        page = doc[page_idx]
        widgets = {
            int(widget.xref): widget
            for widget in (page.widgets() or [])
            if widget.field_type == pymupdf.PDF_WIDGET_TYPE_TEXT
        }
        grouped: dict[int, list[dict]] = {}
        for op in ops:
            grouped.setdefault(int(op["widget_xref"]), []).append(op)

        for widget_xref, replacements in grouped.items():
            widget = widgets.get(widget_xref)
            if widget is None:
                logger.warning(
                    "Could not resolve PDF widget xref=%s on page=%s",
                    widget_xref,
                    page_idx,
                )
                continue

            current_text = str(widget.field_value or "")
            if not current_text:
                continue

            search_cursor = 0
            changed = False
            for replacement in replacements:
                entity_text = replacement["entity_text"]
                span = _find_flexible(current_text, entity_text, start=search_cursor)
                if span is None:
                    span = _find_flexible(current_text, entity_text, start=0)
                if span is None:
                    logger.warning(
                        "Could not map widget label '%s' in widget '%s' on page=%s",
                        entity_text,
                        replacement.get("field_name") or widget.field_name,
                        page_idx,
                    )
                    continue

                token_text = _fit_widget_token(
                    replacement["widget_info"],
                    current_text,
                    span,
                    replacement["logical_token"],
                )
                current_text = (
                    f"{current_text[: span[0]]}{token_text}{current_text[span[1] :]}"
                )
                search_cursor = span[0] + len(token_text)
                changed = True

            if not changed:
                continue

            try:
                widget.field_value = current_text
                widget.update()
            except Exception as exc:
                logger.warning(
                    "Failed to update PDF widget '%s' on page=%s: %s",
                    widget.field_name,
                    page_idx,
                    exc,
                )


def _prepare_signature_widget_ops(
    doc: pymupdf.Document,
    signature_widget_ops: dict[int, list[dict]],
) -> None:
    """
    Deletes signature widgets and prepares their replacement operations.

    Args:
        doc (pymupdf.Document): The PDF document being processed.
        signature_widget_ops (dict[int, list[dict]]): The collected signature widget operations grouped by page index.
    """
    for page_idx, ops in signature_widget_ops.items():
        if not ops:
            continue

        page = doc[page_idx]
        widgets = {
            int(widget.xref): widget
            for widget in (page.widgets() or [])
            if widget.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE
        }
        grouped: dict[int, list[dict]] = {}
        for op in ops:
            grouped.setdefault(int(op["widget_xref"]), []).append(op)

        for widget_xref, widget_group_ops in grouped.items():
            widget = widgets.get(widget_xref)
            widget_rect = pymupdf.Rect(
                widget_group_ops[0].get("widget_rect") or (0, 0, 0, 0)
            )

            if widget is not None:
                widget_rect = pymupdf.Rect(widget.rect)
                try:
                    page.delete_widget(widget)
                except Exception as exc:
                    logger.warning(
                        "Failed to delete signature widget xref=%s on page=%s: %s",
                        widget_xref,
                        page_idx,
                        exc,
                    )
            else:
                logger.warning(
                    "Could not resolve PDF signature widget xref=%s on page=%s",
                    widget_xref,
                    page_idx,
                )

            for op in widget_group_ops:
                op["widget_rect"] = pymupdf.Rect(widget_rect)
                op["asset_rect"] = pymupdf.Rect(widget_rect)
                op["graphics_mode"] = pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED
                op["background_rect"] = _signature_background_rect(op, widget_rect)
