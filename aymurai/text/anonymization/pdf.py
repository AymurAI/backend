from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from unicodedata import normalize

import cv2
import numpy as np
import pymupdf
import pymupdf.layout  # noqa: F401  # activates layout support
from jiwer import cer
from pymupdf4llm.helpers import document_layout as pymupdf4llm_document_layout

from aymurai.logger import get_logger
from aymurai.text.anonymization.alignment import resolve_render_token
from aymurai.text.anonymization.base import (
    BaseAnonymizer,
    InvalidDocumentAnonymizer,
    register_anonymizer,
)

logger = get_logger(__name__)

WATERMARK_TEXT = "Documento anonimizado por AymurAI | https://www.aymurai.info/"

TEXT_FLAG_ITALIC = 2
TEXT_FLAG_SERIF = 4
TEXT_FLAG_MONOSPACED = 8
TEXT_FLAG_BOLD = 16
PDF_TAG_MIN_FONT_SIZE = 7.0
PDF_TAG_FONT_STEP = 0.5
PDF_TAG_MAX_ABBREVIATION = 3
PDF_TAG_RECT_X_PADDING = 0.5
PDF_TAG_RECT_Y_PADDING = 0.0
PDF_TAG_RECT_INSET = 0.5
PDF_TAG_RECT_GAP_FACTOR = 0.5
PDF_TAG_RECT_GAP_MIN = 3.0
PDF_TAG_RECT_GAP_MAX = 8.0

# Vertical overlap ratio required to consider two image rects as matching
_IMAGE_OVERLAP_THRESHOLD = 0.3

# DPI used to rasterise PDF image regions for OpenCV editing.
_IMAGE_EDIT_DPI = 200
_IMAGE_EDIT_MASK_DILATE = 1
_IMAGE_EDIT_INPAINT_RADIUS = 3


def _line_text(line: dict) -> str:
    return "".join(span.get("text", "") for span in line.get("spans", []))


def _rect_tuple(value: Any) -> tuple[float, float, float, float]:
    if isinstance(value, pymupdf.Rect):
        return (float(value.x0), float(value.y0), float(value.x1), float(value.y1))
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
    raise ValueError(f"Invalid rectangle value: {value}")


def _default_style(fallback_size: float = 10.0) -> dict[str, Any]:
    return {
        "font": "",
        "flags": 0,
        "color": (0.0, 0.0, 0.0),
        "size": fallback_size,
        "ascender": 0.8,
        "descender": -0.2,
    }


def _span_text_weight(span: dict) -> tuple[int, float]:
    text = str(span.get("text") or "").strip()
    return (len(text), float(span.get("size") or 0.0))


def _pdf_color_from_span(span: dict) -> tuple[float, float, float]:
    try:
        return tuple(
            float(value) for value in pymupdf.sRGB_to_pdf(int(span.get("color") or 0))
        )
    except Exception:
        return (0.0, 0.0, 0.0)


def _line_style(line: dict, fallback_size: float = 10.0) -> dict[str, Any]:
    spans = [
        span for span in line.get("spans") or [] if str(span.get("text") or "").strip()
    ]
    if not spans:
        return _default_style(fallback_size)

    dominant = max(spans, key=_span_text_weight)
    return {
        "font": str(dominant.get("font") or ""),
        "flags": int(dominant.get("flags") or 0),
        "color": _pdf_color_from_span(dominant),
        "size": float(dominant.get("size") or fallback_size),
        "ascender": float(dominant.get("ascender") or 0.8),
        "descender": float(dominant.get("descender") or -0.2),
    }


def _build_spans_detail(line: dict) -> tuple[list[dict], int]:
    """Build per-span style info with character offsets for entity-level
    style lookup.  Returns ``(spans_detail, strip_offset)``."""
    raw_text = normalize("NFKC", _line_text(line))
    strip_offset = len(raw_text) - len(raw_text.lstrip())

    spans_detail: list[dict] = []
    cursor = 0
    for span in line.get("spans", []):
        span_text = normalize("NFKC", span.get("text", ""))
        span_start = cursor
        cursor += len(span_text)
        spans_detail.append(
            {
                "start": span_start,
                "end": cursor,
                "style": {
                    "font": str(span.get("font") or ""),
                    "flags": int(span.get("flags") or 0),
                    "color": _pdf_color_from_span(span),
                    "size": float(span.get("size") or 10.0),
                    "ascender": float(span.get("ascender") or 0.8),
                    "descender": float(span.get("descender") or -0.2),
                },
            }
        )
    return spans_detail, strip_offset


def _entity_style_from_spans(
    line_entry: dict,
    offset_in_stripped_text: int,
) -> dict[str, Any]:
    """Return the style of the span at *offset_in_stripped_text* within the
    line entry's (stripped) text.  Falls back to line-level dominant style."""
    spans_detail = line_entry.get("spans_detail")
    if not spans_detail:
        return line_entry.get("style") or _default_style()

    strip_offset = line_entry.get("strip_offset", 0)
    raw_offset = offset_in_stripped_text + strip_offset

    for span_info in spans_detail:
        if span_info["start"] <= raw_offset < span_info["end"]:
            return span_info["style"]

    return line_entry.get("style") or _default_style()


def _font_size(line: dict, fallback: float = 10.0) -> float:
    spans = line.get("spans") or []
    sizes = [float(span.get("size")) for span in spans if span.get("size")]
    if not sizes:
        return fallback
    size = sum(sizes) / len(sizes)
    return max(size * 0.9, PDF_TAG_MIN_FONT_SIZE)


def _style_flags(style: dict[str, Any]) -> tuple[bool, bool, bool, bool]:
    flags = int(style.get("flags") or 0)
    font_label = str(style.get("font") or "").lower()

    is_bold = bool(flags & TEXT_FLAG_BOLD) or "bold" in font_label
    is_italic = bool(flags & TEXT_FLAG_ITALIC) or any(
        token in font_label for token in ("italic", "oblique")
    )
    is_mono = bool(flags & TEXT_FLAG_MONOSPACED) or any(
        token in font_label for token in ("courier", "mono", "console")
    )
    is_serif = bool(flags & TEXT_FLAG_SERIF) or any(
        token in font_label
        for token in ("times", "serif", "georgia", "garamond", "mistral")
    )
    return is_bold, is_italic, is_mono, is_serif


def _base14_fontname_for_style(style: dict[str, Any]) -> str:
    """Return a Base-14 font name based on detected style flags."""
    is_bold, is_italic, is_mono, is_serif = _style_flags(style)

    if is_mono:
        family = "Courier"
    elif is_serif:
        family = "Times"
    else:
        family = "Helvetica"

    variants = {
        ("Helvetica", False, False): "Helvetica",
        ("Helvetica", True, False): "Helvetica-Bold",
        ("Helvetica", False, True): "Helvetica-Oblique",
        ("Helvetica", True, True): "Helvetica-BoldOblique",
        ("Times", False, False): "Times-Roman",
        ("Times", True, False): "Times-Bold",
        ("Times", False, True): "Times-Italic",
        ("Times", True, True): "Times-BoldItalic",
        ("Courier", False, False): "Courier",
        ("Courier", True, False): "Courier-Bold",
        ("Courier", False, True): "Courier-Oblique",
        ("Courier", True, True): "Courier-BoldOblique",
    }
    return variants[(family, is_bold, is_italic)]


def _build_flexible_pattern(text: str) -> str:
    tokens = [re.escape(tok) for tok in re.split(r"\s+", text.strip()) if tok]
    return r"\s+".join(tokens)


def _find_flexible(
    haystack: str,
    needle: str,
    start: int = 0,
) -> tuple[int, int] | None:
    if not needle:
        return None

    idx = haystack.find(needle, start)
    if idx >= 0:
        return idx, idx + len(needle)

    pattern = _build_flexible_pattern(needle)
    if not pattern:
        return None

    match = re.search(pattern, haystack[start:])
    if match:
        return start + match.start(), start + match.end()

    if start > 0:
        match = re.search(pattern, haystack)
        if match:
            return match.start(), match.end()

    return None


def _label_start(label: dict) -> int:
    attrs = label.get("attrs") or {}
    alt = attrs.get("aymurai_alt_start_char")
    start = label.get("start_char")
    return int(alt if alt is not None else (start or 0))


def _label_end(label: dict) -> int:
    attrs = label.get("attrs") or {}
    alt = attrs.get("aymurai_alt_end_char")
    end = label.get("end_char")
    return int(alt if alt is not None else (end or 0))


def _label_surface_text(label: dict, document: str) -> str:
    attrs = label.get("attrs") or {}

    # Prefer explicit alt text when the key is present
    if "aymurai_alt_text" in attrs:
        alt_text = attrs["aymurai_alt_text"]
        return str(alt_text) if alt_text else ""

    # Use alt char offsets when available
    alt_start = attrs.get("aymurai_alt_start_char")
    alt_end = attrs.get("aymurai_alt_end_char")

    if alt_start is not None and alt_end is not None:
        start, end = int(alt_start), int(alt_end)
        if 0 <= start < end <= len(document):
            return document[start:end]
        # Alt range is empty/invalid — alt processing cleared this label
        return ""

    # If alt keys exist but values are None, alt processing cleared this label
    if "aymurai_alt_start_char" in attrs and alt_start is None:
        return ""

    # No alt info available; use raw char offsets
    start = int(label.get("start_char") or 0)
    end = int(label.get("end_char") or 0)
    if 0 <= start < end <= len(document):
        return document[start:end]

    text = label.get("text")
    return str(text) if text else ""


def _same_boundary_candidate(left: dict, right: dict) -> bool:
    left_attrs = left.get("attrs") or {}
    right_attrs = right.get("attrs") or {}

    if left_attrs.get("aymurai_label") != right_attrs.get("aymurai_label"):
        return False

    left_cid = left_attrs.get("canonical_entity_id")
    right_cid = right_attrs.get("canonical_entity_id")
    if left_cid and right_cid and str(left_cid) != str(right_cid):
        return False

    left_text = str(left.get("text") or "").strip()
    right_text = str(right.get("text") or "").strip()
    return bool(left_text and right_text)


def _resolve_token(label: dict, render_context: dict[str, Any] | None) -> str:
    boundary_token = label.get("_boundary_token")
    if boundary_token:
        return boundary_token

    token = resolve_render_token(label, render_context)
    return token or "ENT"


def _token_parts(token: str) -> tuple[str, str | None]:
    match = re.match(r"^(.*?)(?:_(\d+))?$", token)
    if not match:
        normalized = token.strip() or "ENT"
        return normalized, None

    base = match.group(1).strip() or "ENT"
    suffix = match.group(2)
    return base, suffix


def _abbreviate_token(base: str, length: int) -> str:
    normalized = "".join(char for char in base.upper() if char.isalnum())
    if not normalized:
        normalized = "ENT"
    return normalized[:length] or normalized[:1] or "E"


def _build_display_token_candidates(token: str) -> list[str]:
    base, suffix = _token_parts(token.upper())
    candidates: list[str] = []

    def add(value: str) -> None:
        if value and value not in candidates:
            candidates.append(value)

    if suffix:
        add(f"<{base}_{suffix}>")
    add(f"<{base}>")

    for length in (PDF_TAG_MAX_ABBREVIATION, 1):
        abbreviated = _abbreviate_token(base, length)
        if suffix:
            add(f"<{abbreviated}_{suffix}>")
        add(f"<{abbreviated}>")

    return candidates


def _iter_font_sizes(start_size: float) -> list[float]:
    if start_size <= 0:
        return []

    sizes: list[float] = [start_size]
    current = start_size
    while current - PDF_TAG_FONT_STEP >= PDF_TAG_MIN_FONT_SIZE - 1e-6:
        current = round(current - PDF_TAG_FONT_STEP, 2)
        if current not in sizes:
            sizes.append(current)

    return sizes


def _fit_display_token(
    token: str,
    rect: pymupdf.Rect,
    fontname: str,
    base_font_size: float,
    font_obj: pymupdf.Font | None = None,
) -> tuple[str | None, float | None]:
    """Find the best display candidate that fits inside *rect*.

    When *font_obj* is provided its ``text_length`` method is used for pixel-
    accurate measurement; otherwise the Base-14 ``pymupdf.get_text_length``
    function is used as a fallback.
    """
    if rect.width <= 0 or rect.height <= 0:
        return None, None

    available_width = max(rect.width - (2 * PDF_TAG_RECT_INSET), 1.0)
    start_size = min(base_font_size, max(rect.height - 1.0, 1.0))
    if start_size < 1.0:
        return None, None

    def _measure(text: str, size: float) -> float:
        if font_obj is not None:
            try:
                return font_obj.text_length(text, fontsize=size)
            except Exception:
                pass
        return pymupdf.get_text_length(text, fontname=fontname, fontsize=size)

    for size in _iter_font_sizes(start_size):
        for candidate in _build_display_token_candidates(token):
            if _measure(candidate, size) <= available_width + 0.1:
                return candidate, size

    return None, None


# Cache of Base-14 pymupdf.Font objects (they are reusable and thread-safe).
_BASE14_FONT_CACHE: dict[str, pymupdf.Font] = {}


def _get_base14_font(style: dict[str, Any]) -> pymupdf.Font:
    """Return a ``pymupdf.Font`` built from the Base-14 name that matches
    *style*.  The object is cached so repeated calls are essentially free.

    Base-14 fonts always contain the full Latin character set (including
    ``<``, ``>``, ``_``, digits) and correctly carry bold / italic weight,
    unlike subset font buffers extracted from the PDF."""
    name = _base14_fontname_for_style(style)
    font = _BASE14_FONT_CACHE.get(name)
    if font is None:
        font = pymupdf.Font(name)
        _BASE14_FONT_CACHE[name] = font
    return font


def _apply_minimal_boundary_merge(
    paragraphs: list[dict],
    render_context: dict[str, Any] | None,
) -> None:
    for left_par, right_par in zip(paragraphs, paragraphs[1:]):
        left_doc = left_par.get("document") or ""
        right_doc = right_par.get("document") or ""
        left_labels = left_par.get("labels") or []
        right_labels = right_par.get("labels") or []

        if not left_doc or not right_doc or not left_labels or not right_labels:
            continue

        left_candidates = [
            label
            for label in left_labels
            if _label_end(label) >= max(0, len(left_doc) - 2)
        ]
        right_candidates = [label for label in right_labels if _label_start(label) <= 2]

        if not left_candidates or not right_candidates:
            continue

        for left_label in left_candidates:
            for right_label in right_candidates:
                if not _same_boundary_candidate(left_label, right_label):
                    continue

                shared_token = _resolve_token(left_label, render_context)
                if not shared_token:
                    shared_token = _resolve_token(right_label, render_context)
                if shared_token:
                    left_label["_boundary_token"] = shared_token
                    right_label["_boundary_token"] = shared_token
                break


def _build_layout_paragraphs(parsed_doc: Any) -> list[dict]:
    chunks = parsed_doc.to_text(
        page_chunks=True,
        header=True,
        footer=True,
        show_progress=False,
    )

    paragraphs: list[dict] = []
    layout_index = 0
    for page_idx, (page, chunk) in enumerate(zip(parsed_doc.pages, chunks)):
        page_text = chunk.get("text") or ""
        page_boxes = chunk.get("page_boxes") or []

        for box_meta in page_boxes:
            box_idx = int(box_meta["index"])
            if box_idx >= len(page.boxes):
                continue

            start, stop = box_meta.get("pos", (0, 0))
            box_text = normalize("NFKC", page_text[start:stop]).strip()
            if not box_text:
                continue

            box = page.boxes[box_idx]
            line_entries: list[dict] = []
            line_text_chunks: list[str] = []
            line_cursor = 0

            for line_idx, line in enumerate(box.textlines or []):
                text = normalize("NFKC", _line_text(line)).strip()
                if not text:
                    continue

                if line_text_chunks:
                    line_text_chunks.append("\n")
                    line_cursor += 1

                line_start = line_cursor
                line_text_chunks.append(text)
                line_cursor += len(text)
                line_end = line_cursor
                style = _line_style(line)
                spans_detail, strip_offset = _build_spans_detail(line)

                line_entries.append(
                    {
                        "page_index": page_idx,
                        "box_index": box_idx,
                        "line_index": line_idx,
                        "bbox": _rect_tuple(line["bbox"]),
                        "font_size": _font_size(line, float(style.get("size") or 10.0)),
                        "start": line_start,
                        "end": line_end,
                        "text": text,
                        "style": style,
                        "spans_detail": spans_detail,
                        "strip_offset": strip_offset,
                    }
                )

            line_text = "".join(line_text_chunks)
            if not line_text:
                continue

            paragraphs.append(
                {
                    "plain_text": box_text,
                    "metadata": {
                        "layout_index": layout_index,
                        "page_index": page_idx,
                        "page_number": page.page_number,
                        "box_index": box_idx,
                        "boxclass": box.boxclass,
                        "box_bbox": (
                            float(box.x0),
                            float(box.y0),
                            float(box.x1),
                            float(box.y1),
                        ),
                        "line_text": line_text,
                        "lines": line_entries,
                    },
                }
            )
            layout_index += 1

    return paragraphs


def _match_predictions_to_layout(
    layout_paragraphs: list[dict],
    preds: list[dict],
) -> list[dict]:
    if not layout_paragraphs or not preds:
        return []

    available_indices = list(range(len(layout_paragraphs)))
    all_indices = list(range(len(layout_paragraphs)))
    matched: list[dict] = []

    normalized_layout_texts = [
        normalize("NFKC", paragraph["plain_text"]).strip()
        for paragraph in layout_paragraphs
    ]

    for pred_idx, pred in enumerate(preds):
        pred_text = normalize("NFKC", str(pred.get("document") or "")).strip()
        if not pred_text:
            continue

        candidate_pool = available_indices if available_indices else all_indices
        exact_idx = next(
            (
                idx
                for idx in candidate_pool
                if normalized_layout_texts[idx] == pred_text
            ),
            None,
        )

        if exact_idx is None:
            exact_idx = min(
                candidate_pool,
                key=lambda idx: cer(pred_text, normalized_layout_texts[idx]),
            )

        paragraph = deepcopy(layout_paragraphs[exact_idx])
        paragraph["document"] = pred.get("document") or ""
        paragraph["labels"] = pred.get("labels") or []
        paragraph["pred_index"] = pred_idx
        matched.append(paragraph)

        if exact_idx in available_indices:
            available_indices.remove(exact_idx)

    matched.sort(key=lambda paragraph: paragraph["metadata"]["layout_index"])
    return matched


def _rect_vertical_overlap(left: pymupdf.Rect, right: pymupdf.Rect) -> float:
    overlap = max(0.0, min(left.y1, right.y1) - max(left.y0, right.y0))
    min_height = max(min(left.height, right.height), 1e-6)
    return overlap / min_height


def _group_adjacent_rects(
    rects: list[pymupdf.Rect], max_gap: float
) -> list[pymupdf.Rect]:
    if not rects:
        return []

    ordered = sorted(rects, key=lambda rect: (rect.y0, rect.x0, rect.x1))
    groups: list[list[pymupdf.Rect]] = [[ordered[0]]]

    for rect in ordered[1:]:
        previous = groups[-1][-1]
        gap = rect.x0 - previous.x1
        if _rect_vertical_overlap(previous, rect) >= 0.5 and gap <= max_gap:
            groups[-1].append(rect)
        else:
            groups.append([rect])

    merged_rects: list[pymupdf.Rect] = []
    for group in groups:
        merged = pymupdf.Rect(group[0])
        for rect in group[1:]:
            merged.include_rect(rect)
        merged_rects.append(merged)

    return merged_rects


def _pick_rect_group_for_segment(
    page: pymupdf.Page,
    line: dict,
    text: str,
    line_x_cursor: dict[tuple[int, int, int], float],
) -> pymupdf.Rect:
    clip = pymupdf.Rect(line["bbox"])
    rects = [rect for rect in page.search_for(text, clip=clip) if rect.intersects(clip)]
    if not rects:
        return clip

    max_gap = min(
        max(clip.height * PDF_TAG_RECT_GAP_FACTOR, PDF_TAG_RECT_GAP_MIN),
        PDF_TAG_RECT_GAP_MAX,
    )
    grouped_rects = _group_adjacent_rects(rects, max_gap=max_gap)

    line_key = (line["page_index"], line["box_index"], line["line_index"])
    min_x = line_x_cursor.get(line_key, clip.x0 - 1)

    for rect in grouped_rects:
        if rect.x0 >= min_x - 0.5:
            line_x_cursor[line_key] = rect.x1
            return rect

    chosen = grouped_rects[0]
    line_x_cursor[line_key] = chosen.x1
    return chosen


def _padded_rect(rect: pymupdf.Rect, clip: pymupdf.Rect) -> pymupdf.Rect:
    padded = pymupdf.Rect(rect)
    padded.x0 = max(clip.x0, padded.x0 - PDF_TAG_RECT_X_PADDING)
    padded.y0 = max(clip.y0, padded.y0 - PDF_TAG_RECT_Y_PADDING)
    padded.x1 = min(clip.x1, padded.x1 + PDF_TAG_RECT_X_PADDING)
    padded.y1 = min(clip.y1, padded.y1 + PDF_TAG_RECT_Y_PADDING)
    return padded


def _render_rect(rect: pymupdf.Rect) -> pymupdf.Rect:
    render_rect = pymupdf.Rect(rect)
    inset = min(PDF_TAG_RECT_INSET, max(render_rect.height * 0.1, 0.0))
    render_rect.x0 += inset
    render_rect.x1 -= inset
    if render_rect.x1 <= render_rect.x0:
        render_rect = pymupdf.Rect(rect)
    return render_rect


def _text_redact_rect(rect: pymupdf.Rect) -> pymupdf.Rect:
    redact_rect = pymupdf.Rect(rect)
    edge_inset = min(0.25, max(redact_rect.width * 0.01, 0.05))
    if redact_rect.width > (2 * edge_inset):
        redact_rect.x0 += edge_inset
        redact_rect.x1 -= edge_inset
    return redact_rect


def _normalize_line_chars(spans: list[dict]) -> list[dict[str, Any]]:
    chars: list[dict[str, Any]] = []
    for span in spans:
        for char in span.get("chars") or []:
            norm_text = normalize("NFKC", str(char.get("c") or ""))
            if not norm_text:
                continue
            bbox = pymupdf.Rect(char["bbox"])
            for norm_char in norm_text:
                chars.append({"char": norm_char, "bbox": bbox})
    return chars


def _line_chars_from_page(page: pymupdf.Page, line: dict) -> list[dict[str, Any]]:
    clip = pymupdf.Rect(line["bbox"])
    raw = page.get_text("rawdict", clip=clip)
    target_text = normalize("NFKC", str(line.get("text") or "")).strip()

    best_chars: list[dict[str, Any]] = []
    best_score: tuple[float, float, float] | None = None

    for block in raw.get("blocks") or []:
        if block.get("type", 0) != 0:
            continue
        for raw_line in block.get("lines") or []:
            chars = _normalize_line_chars(raw_line.get("spans") or [])
            if not chars:
                continue

            candidate_rect = pymupdf.Rect(raw_line["bbox"])
            candidate_text = "".join(entry["char"] for entry in chars).strip()
            overlap = (
                _rect_vertical_overlap(candidate_rect, clip)
                if candidate_rect.intersects(clip)
                else 0.0
            )
            text_score = 0.0
            if target_text or candidate_text:
                text_score = (
                    0.0
                    if target_text == candidate_text
                    else cer(target_text, candidate_text)
                )
            bbox_score = (
                abs(candidate_rect.x0 - clip.x0)
                + abs(candidate_rect.y0 - clip.y0)
                + abs(candidate_rect.x1 - clip.x1)
                + abs(candidate_rect.y1 - clip.y1)
            ) / 100.0
            score = (1.0 - overlap, text_score, bbox_score)
            if best_score is None or score < best_score:
                best_score = score
                best_chars = chars

    return best_chars


def _rect_from_char_slice(
    chars: list[dict[str, Any]],
    start: int,
    end: int,
) -> pymupdf.Rect | None:
    if not chars:
        return None

    slice_start = max(int(start), 0)
    slice_end = min(int(end), len(chars))
    if slice_end <= slice_start:
        return None

    segment = chars[slice_start:slice_end]
    if not segment:
        return None

    boxes = [entry["bbox"] for entry in segment if str(entry["char"]).strip()]
    if not boxes:
        boxes = [entry["bbox"] for entry in segment]
    if not boxes:
        return None

    rect = pymupdf.Rect(boxes[0])
    for bbox in boxes[1:]:
        rect.include_rect(bbox)
    return rect


def _build_page_op(
    rect: pymupdf.Rect,
    line: dict | None,
    token: str,
    is_image: bool = False,
    entity_style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    line_clip = pymupdf.Rect(line["bbox"]) if line else pymupdf.Rect(rect)
    canvas_rect = _padded_rect(rect, line_clip)
    render_rect = _render_rect(canvas_rect)
    style = entity_style or (line or {}).get("style") or _default_style()
    base_font_size = float((line or {}).get("font_size") or style.get("size") or 10.0)

    # Always use Base-14 fonts: they carry correct bold/italic weight and
    # contain all glyphs needed for tags (<, >, _, digits, letters).
    # Subset font buffers extracted from the PDF lack many of these glyphs.
    fontname = _base14_fontname_for_style(style)
    font_obj = _get_base14_font(style)

    display_token, fitted_size = _fit_display_token(
        token,
        render_rect,
        fontname,
        base_font_size,
        font_obj=font_obj,
    )

    if not display_token or fitted_size is None:
        logger.warning(
            "Could not fit PDF token '%s' inside rect=%s",
            token,
            tuple(round(value, 2) for value in canvas_rect),
        )

    return {
        "redact_rect": _text_redact_rect(rect),
        "canvas_rect": canvas_rect,
        "render_rect": render_rect,
        "line_rect": line_clip,
        "text": display_token,
        "logical_token": token,
        "fontname": fontname,
        "fontsize": fitted_size,
        "text_align": pymupdf.TEXT_ALIGN_LEFT,
        "text_color": style.get("color") or (0.0, 0.0, 0.0),
        "is_image": is_image,
        "skip_background_fill": is_image,
        "style": style,
    }


def _image_rects_for_clip(
    page: pymupdf.Page,
    clip: pymupdf.Rect,
) -> list[pymupdf.Rect]:
    """Return bounding rectangles of images that overlap *clip*."""
    rects: list[pymupdf.Rect] = []
    for img_info in page.get_image_info():
        bbox = img_info.get("bbox")
        if bbox is None:
            continue
        img_rect = pymupdf.Rect(bbox)
        if img_rect.intersects(clip) and img_rect.get_area() > 0:
            rects.append(img_rect)
    return rects


def _entity_overlaps_image(
    page: pymupdf.Page,
    entity_rect: pymupdf.Rect,
    image_rects: list[pymupdf.Rect],
) -> pymupdf.Rect | None:
    """If *entity_rect* overlaps an image return the image rect, else None."""
    for img_rect in image_rects:
        overlap = _rect_vertical_overlap(entity_rect, img_rect)
        if overlap >= _IMAGE_OVERLAP_THRESHOLD and entity_rect.intersects(img_rect):
            return img_rect
    return None


def _widget_text_color(widget: pymupdf.Widget) -> tuple[float, float, float]:
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
    return {
        "font": str(widget.text_font or ""),
        "flags": 0,
        "color": _widget_text_color(widget),
        "size": float(widget.text_fontsize or 10.0),
        "ascender": 0.8,
        "descender": -0.2,
    }


def _page_widget_infos(page: pymupdf.Page) -> list[dict[str, Any]]:
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


def _apply_signature_widget_ops(
    doc: pymupdf.Document,
    signature_widget_ops: dict[int, list[dict]],
) -> None:
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
            widget_rect = pymupdf.Rect(widget_group_ops[0]["widget_rect"])

            try:
                pix = page.get_pixmap(
                    clip=widget_rect,
                    matrix=pymupdf.Matrix(
                        _IMAGE_EDIT_DPI / 72.0, _IMAGE_EDIT_DPI / 72.0
                    ),
                    alpha=False,
                )
            except Exception as exc:
                logger.warning(
                    "Could not rasterise signature widget xref=%s on page=%s: %s",
                    widget_xref,
                    page_idx,
                    exc,
                )
                pix = None

            widget = widgets.get(widget_xref)
            if widget is not None:
                try:
                    page.delete_widget(widget)
                except Exception as exc:
                    logger.warning(
                        "Failed to delete signature widget xref=%s on page=%s: %s",
                        widget_xref,
                        page_idx,
                        exc,
                    )

            if pix is None:
                page.draw_rect(
                    widget_rect,
                    color=(1, 1, 1),
                    fill=(1, 1, 1),
                    width=0,
                    overlay=True,
                )
            else:
                img = (
                    np.frombuffer(pix.samples, dtype=np.uint8)
                    .reshape(pix.height, pix.width, pix.n)
                    .copy()
                )
                if pix.n >= 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

                scale = _IMAGE_EDIT_DPI / 72.0
                mask = np.zeros(img.shape[:2], dtype=np.uint8)
                for op in widget_group_ops:
                    canvas = op["canvas_rect"]
                    x0 = max(int((canvas.x0 - widget_rect.x0) * scale), 0)
                    y0 = max(int((canvas.y0 - widget_rect.y0) * scale), 0)
                    x1 = min(int((canvas.x1 - widget_rect.x0) * scale), img.shape[1])
                    y1 = min(int((canvas.y1 - widget_rect.y0) * scale), img.shape[0])
                    if x1 <= x0 or y1 <= y0:
                        continue
                    mask[y0:y1, x0:x1] = 255

                if np.any(mask):
                    if _IMAGE_EDIT_MASK_DILATE > 0:
                        kernel = np.ones((3, 3), dtype=np.uint8)
                        mask = cv2.dilate(
                            mask, kernel, iterations=_IMAGE_EDIT_MASK_DILATE
                        )
                    try:
                        img = cv2.inpaint(
                            img,
                            mask,
                            _IMAGE_EDIT_INPAINT_RADIUS,
                            cv2.INPAINT_TELEA,
                        )
                    except Exception as exc:
                        logger.warning(
                            "OpenCV inpaint failed for signature widget xref=%s on page=%s: %s",
                            widget_xref,
                            page_idx,
                            exc,
                        )
                        img[mask > 0] = 255

                success, png_buf = cv2.imencode(".png", img)
                if success:
                    try:
                        page.insert_image(
                            widget_rect, stream=png_buf.tobytes(), overlay=True
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to insert edited signature widget image xref=%s on page=%s: %s",
                            widget_xref,
                            page_idx,
                            exc,
                        )
                        page.draw_rect(
                            widget_rect,
                            color=(1, 1, 1),
                            fill=(1, 1, 1),
                            width=0,
                            overlay=True,
                        )
                else:
                    page.draw_rect(
                        widget_rect,
                        color=(1, 1, 1),
                        fill=(1, 1, 1),
                        width=0,
                        overlay=True,
                    )

            for op in widget_group_ops:
                _render_text_op(page, op)


def _collect_page_redactions(
    doc: pymupdf.Document,
    paragraphs: list[dict],
    render_context: dict[str, Any] | None,
) -> dict[int, list[dict]]:
    page_ops: dict[int, list[dict]] = {}
    widget_ops: dict[int, list[dict]] = {}
    signature_widget_ops: dict[int, list[dict]] = {}
    line_x_cursor: dict[tuple[int, int, int], float] = {}
    line_char_cache: dict[tuple[int, int, int], list[dict[str, Any]]] = {}

    # Pre-compute image rects and widgets per page
    page_image_rects: dict[int, list[pymupdf.Rect]] = {}
    page_widgets: dict[int, list[dict[str, Any]]] = {}

    for paragraph in paragraphs:
        metadata = paragraph.get("metadata") or {}
        lines = metadata.get("lines") or []
        if not lines:
            continue

        page_index = int(metadata["page_index"])
        page = doc[page_index]
        line_text = metadata.get("line_text") or ""
        box_clip = pymupdf.Rect(metadata.get("box_bbox") or page.rect)
        document = paragraph.get("document") or ""
        labels = sorted(paragraph.get("labels") or [], key=_label_start)
        search_cursor = 0

        # Lazy-load image rects and widget infos for this page
        if page_index not in page_image_rects:
            page_image_rects[page_index] = _image_rects_for_clip(page, page.rect)
        if page_index not in page_widgets:
            page_widgets[page_index] = _page_widget_infos(page)

        for label in labels:
            entity_text = _label_surface_text(label, document).strip()
            if not entity_text:
                # Fall back to raw label text only if alt processing was
                # not applied (no alt attributes present at all).
                attrs = label.get("attrs") or {}
                alt_applied = any(
                    key in attrs
                    for key in (
                        "aymurai_alt_text",
                        "aymurai_alt_start_char",
                        "aymurai_alt_end_char",
                    )
                )
                if not alt_applied:
                    entity_text = str(label.get("text") or "").strip()
            if not entity_text:
                continue

            token = _resolve_token(label, render_context)

            span = _find_flexible(line_text, entity_text, start=search_cursor)
            if span is None:
                span = _find_flexible(line_text, entity_text, start=0)
            if span is None:
                # -- Fallback: direct page search --
                fallback_rects = [
                    rect
                    for rect in page.search_for(entity_text, clip=box_clip)
                    if rect.intersects(box_clip)
                ]

                # Check if this is a widget-backed entity before falling back to images
                if fallback_rects:
                    fallback_widget = _entity_overlaps_widget(
                        fallback_rects[0],
                        page_widgets[page_index],
                    )
                    if fallback_widget is not None:
                        if (
                            fallback_widget["field_type"]
                            == pymupdf.PDF_WIDGET_TYPE_TEXT
                        ):
                            widget_ops.setdefault(page_index, []).append(
                                {
                                    "widget_xref": fallback_widget["xref"],
                                    "field_name": fallback_widget["field_name"],
                                    "widget_info": fallback_widget,
                                    "entity_text": entity_text,
                                    "logical_token": token,
                                }
                            )
                            continue
                        if (
                            fallback_widget["field_type"]
                            == pymupdf.PDF_WIDGET_TYPE_SIGNATURE
                        ):
                            op = _build_page_op(
                                fallback_rects[0],
                                lines[0] if lines else None,
                                token,
                                entity_style=fallback_widget.get("style") or None,
                            )
                            op["skip_background_fill"] = True
                            op["widget_xref"] = fallback_widget["xref"]
                            op["widget_rect"] = fallback_widget["rect"]
                            signature_widget_ops.setdefault(page_index, []).append(op)
                            continue

                # Check if this is an image-based entity
                if not fallback_rects:
                    img_match = _try_image_entity(
                        page,
                        entity_text,
                        box_clip,
                        page_image_rects[page_index],
                    )
                    if img_match is not None:
                        op = _build_page_op(
                            img_match,
                            lines[0] if lines else None,
                            token,
                            is_image=True,
                        )
                        op["image_rect"] = img_match
                        page_ops.setdefault(page_index, []).append(op)
                        continue

                if fallback_rects:
                    grouped_rects = _group_adjacent_rects(
                        fallback_rects, max_gap=PDF_TAG_RECT_GAP_MAX
                    )
                    fallback_line = lines[0] if lines else None

                    # Check if any of these rects overlap an image
                    for rect in grouped_rects:
                        img_rect = _entity_overlaps_image(
                            page,
                            rect,
                            page_image_rects[page_index],
                        )
                        op = _build_page_op(
                            rect,
                            fallback_line,
                            token,
                            is_image=(img_rect is not None),
                        )
                        if img_rect is not None:
                            op["image_rect"] = img_rect
                        page_ops.setdefault(page_index, []).append(op)
                    continue

                logger.warning(
                    "Could not map label '%s' on page=%s box=%s",
                    entity_text,
                    metadata.get("page_number"),
                    metadata.get("box_index"),
                )
                continue

            search_cursor = span[1]

            # Collect line segments this entity spans
            segments: list[
                tuple[
                    dict,
                    str,
                    pymupdf.Rect,
                    pymupdf.Rect | None,
                    dict,
                    dict[str, Any] | None,
                ]
            ] = []
            for line in lines:
                overlap_start = max(span[0], line["start"])
                overlap_end = min(span[1], line["end"])
                if overlap_end <= overlap_start:
                    continue

                segment_text = line_text[overlap_start:overlap_end].strip()
                if not segment_text:
                    continue

                line_key = (
                    line["page_index"],
                    line["box_index"],
                    line["line_index"],
                )
                line_chars = line_char_cache.get(line_key)
                if line_chars is None:
                    line_chars = _line_chars_from_page(page, line)
                    line_char_cache[line_key] = line_chars

                raw_start = (
                    overlap_start - line["start"] + int(line.get("strip_offset", 0))
                )
                raw_end = overlap_end - line["start"] + int(line.get("strip_offset", 0))
                rect = _rect_from_char_slice(line_chars, raw_start, raw_end)
                if rect is None:
                    rect = _pick_rect_group_for_segment(
                        page,
                        line,
                        segment_text,
                        line_x_cursor,
                    )

                widget_info = _entity_overlaps_widget(
                    rect,
                    page_widgets[page_index],
                )

                # Check for image overlap
                img_rect = _entity_overlaps_image(
                    page,
                    rect,
                    page_image_rects[page_index],
                )

                # Determine entity-specific style from the span that
                # actually contains this text (not the line's dominant style)
                offset_in_line = overlap_start - line["start"]
                ent_style = _entity_style_from_spans(line, offset_in_line)

                segments.append(
                    (line, segment_text, rect, img_rect, ent_style, widget_info)
                )

            if not segments:
                continue

            if len(segments) == 1:
                # Single-line entity: route widget-backed content through the widget path.
                line, _seg_text, rect, img_rect, ent_style, widget_info = segments[0]
                if widget_info is not None:
                    if widget_info["field_type"] == pymupdf.PDF_WIDGET_TYPE_TEXT:
                        widget_ops.setdefault(page_index, []).append(
                            {
                                "widget_xref": widget_info["xref"],
                                "field_name": widget_info["field_name"],
                                "widget_info": widget_info,
                                "entity_text": entity_text,
                                "logical_token": token,
                            }
                        )
                        continue
                    if widget_info["field_type"] == pymupdf.PDF_WIDGET_TYPE_SIGNATURE:
                        op = _build_page_op(
                            rect,
                            line,
                            token,
                            entity_style=ent_style,
                        )
                        op["skip_background_fill"] = True
                        op["widget_xref"] = widget_info["xref"]
                        op["widget_rect"] = widget_info["rect"]
                        signature_widget_ops.setdefault(page_index, []).append(op)
                        continue

                op = _build_page_op(
                    rect,
                    line,
                    token,
                    is_image=(img_rect is not None),
                    entity_style=ent_style,
                )
                if img_rect is not None:
                    op["image_rect"] = img_rect
                page_ops.setdefault(page_index, []).append(op)
            else:
                # Multi-line entity: write the token on the widest segment only; blank the others.
                widest_idx = max(
                    range(len(segments)),
                    key=lambda i: segments[i][2].width,
                )
                any_image = any(seg[3] is not None for seg in segments)

                signature_widget = None
                if all(seg[5] is not None for seg in segments):
                    widget_xrefs = {int(seg[5]["xref"]) for seg in segments}
                    widget_types = {int(seg[5]["field_type"]) for seg in segments}
                    if len(widget_xrefs) == 1 and widget_types == {
                        pymupdf.PDF_WIDGET_TYPE_SIGNATURE
                    }:
                        signature_widget = segments[0][5]

                for seg_idx, (
                    seg_line,
                    _seg_text,
                    seg_rect,
                    seg_img,
                    seg_style,
                    seg_widget,
                ) in enumerate(segments):
                    if seg_idx == widest_idx:
                        op = _build_page_op(
                            seg_rect,
                            seg_line,
                            token,
                            is_image=(any_image and signature_widget is None),
                            entity_style=seg_style,
                        )
                        if seg_img is not None and signature_widget is None:
                            op["image_rect"] = seg_img
                    else:
                        op = _build_page_op(
                            seg_rect,
                            seg_line,
                            token,
                            is_image=(
                                (seg_img is not None) and signature_widget is None
                            ),
                            entity_style=seg_style,
                        )
                        op["text"] = None
                        op["fontsize"] = None
                        if seg_img is not None and signature_widget is None:
                            op["image_rect"] = seg_img

                    if signature_widget is not None:
                        op["skip_background_fill"] = True
                        op["widget_xref"] = signature_widget["xref"]
                        op["widget_rect"] = signature_widget["rect"]
                        signature_widget_ops.setdefault(page_index, []).append(op)
                    else:
                        page_ops.setdefault(page_index, []).append(op)

    return page_ops, widget_ops, signature_widget_ops


def _try_image_entity(
    page: pymupdf.Page,
    entity_text: str,
    clip: pymupdf.Rect,
    image_rects: list[pymupdf.Rect],
) -> pymupdf.Rect | None:
    """When text search fails, check whether the entity region corresponds to
    an image in the PDF (e.g. a scanned signature or stamp).  If an image
    overlaps the *clip* area, return its bounding rect so we can blank it.

    We try to locate the entity text on the page (ignoring clip) first:
    if the text is found near an image, that image is the match.
    Otherwise we fall back to returning the image with the best spatial
    overlap with *clip*.
    """
    if not image_rects:
        return None

    # Try unclipped text search — the entity might be rendered as real text
    # on top of (or near) an image.
    text_hits = page.search_for(entity_text)
    if text_hits:
        for hit_rect in text_hits:
            for img_rect in image_rects:
                if hit_rect.intersects(img_rect):
                    return img_rect

    # Fallback: pick the image whose intersection with *clip* is largest
    best: pymupdf.Rect | None = None
    best_area = 0.0
    for img_rect in image_rects:
        if not img_rect.intersects(clip) or img_rect.get_area() <= 0:
            continue
        intersection = img_rect & clip
        area = intersection.get_area()
        if area > best_area:
            best_area = area
            best = img_rect

    return best


def _apply_redactions(
    doc: pymupdf.Document,
    page_ops: dict[int, list[dict]],
    widget_ops: dict[int, list[dict]],
    signature_widget_ops: dict[int, list[dict]],
) -> None:
    _apply_widget_ops(doc, widget_ops)
    _apply_signature_widget_ops(doc, signature_widget_ops)

    for page_idx, ops in page_ops.items():
        page = doc[page_idx]

        # Separate image ops from text ops
        text_ops: list[dict] = []
        image_ops: list[dict] = []
        for op in ops:
            if op.get("is_image") and op.get("image_rect") is not None:
                image_ops.append(op)
            else:
                text_ops.append(op)

        # ── Image entities: edit via OpenCV ──────────────────────────
        # Group image ops by their image_rect so we render/edit each
        # image only once even when multiple entities overlap it.
        if image_ops:
            img_groups: dict[tuple, list[dict]] = {}
            for op in image_ops:
                key = _rect_tuple(op["image_rect"])
                img_groups.setdefault(key, []).append(op)

            for rect_key, group_ops in img_groups.items():
                img_rect = pymupdf.Rect(rect_key)
                _edit_image_with_opencv(page, img_rect, group_ops)

        # ── Text entities: standard redact flow ──────────────────────
        # 1) Add text redaction annotations
        for op in text_ops:
            page.add_redact_annot(
                op["redact_rect"],
                text=None,
                fill=(1, 1, 1),
                cross_out=False,
            )

        # 2) Apply text redactions (images are never touched here)
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            text=pymupdf.PDF_REDACT_TEXT_REMOVE,
        )

        # 3) Draw replacement text after the redactions and image edits are in place.
        for op in text_ops:
            _render_text_op(page, op)
        for op in image_ops:
            _render_text_op(page, op)


def _edit_image_with_opencv(
    page: pymupdf.Page,
    img_rect: pymupdf.Rect,
    ops: list[dict],
) -> None:
    """Rasterise *img_rect* from *page*, remove the original entity pixels,
    and overlay the edited image back onto the page.

    Tags are rendered afterwards with the normal PDF text path so they stay
    sharp and aligned with the surrounding text instead of being rasterised by
    OpenCV.
    """
    scale = _IMAGE_EDIT_DPI / 72.0
    mat = pymupdf.Matrix(scale, scale)

    try:
        pix = page.get_pixmap(clip=img_rect, matrix=mat, alpha=False)
    except Exception as exc:
        logger.warning("Could not rasterise image region %s: %s", img_rect, exc)
        page.draw_rect(
            img_rect,
            color=(1, 1, 1),
            fill=(1, 1, 1),
            width=0,
            overlay=True,
        )
        return

    img = (
        np.frombuffer(pix.samples, dtype=np.uint8)
        .reshape(
            pix.height,
            pix.width,
            pix.n,
        )
        .copy()
    )
    if pix.n >= 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    mask = np.zeros(img.shape[:2], dtype=np.uint8)
    for op in ops:
        canvas = op["canvas_rect"]
        x0 = max(int((canvas.x0 - img_rect.x0) * scale), 0)
        y0 = max(int((canvas.y0 - img_rect.y0) * scale), 0)
        x1 = min(int((canvas.x1 - img_rect.x0) * scale), img.shape[1])
        y1 = min(int((canvas.y1 - img_rect.y0) * scale), img.shape[0])

        if x1 <= x0 or y1 <= y0:
            continue

        mask[y0:y1, x0:x1] = 255

    if np.any(mask):
        if _IMAGE_EDIT_MASK_DILATE > 0:
            kernel = np.ones((3, 3), dtype=np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=_IMAGE_EDIT_MASK_DILATE)
        try:
            img = cv2.inpaint(img, mask, _IMAGE_EDIT_INPAINT_RADIUS, cv2.INPAINT_TELEA)
        except Exception as exc:
            logger.warning("OpenCV inpaint failed for rect %s: %s", img_rect, exc)
            img[mask > 0] = 255

    success, png_buf = cv2.imencode(".png", img)
    if not success:
        logger.warning("Failed to encode edited image for rect %s", img_rect)
        page.draw_rect(
            img_rect,
            color=(1, 1, 1),
            fill=(1, 1, 1),
            width=0,
            overlay=True,
        )
        return

    try:
        page.insert_image(img_rect, stream=png_buf.tobytes(), overlay=True)
    except Exception as exc:
        logger.warning(
            "Failed to re-insert edited image for rect %s: %s", img_rect, exc
        )
        page.draw_rect(
            img_rect,
            color=(1, 1, 1),
            fill=(1, 1, 1),
            width=0,
            overlay=True,
        )


def _render_text_op(page: pymupdf.Page, op: dict) -> None:
    """Render a single anonymisation tag onto *page*."""
    canvas = op["canvas_rect"]
    if not op.get("skip_background_fill"):
        page.draw_rect(
            canvas,
            color=(1, 1, 1),
            fill=(1, 1, 1),
            width=0,
            overlay=True,
        )

    if not op.get("text") or not op.get("fontsize"):
        return

    render = op["render_rect"]
    line_rect = pymupdf.Rect(op.get("line_rect") or render)
    style = op.get("style") or {}
    base14_name = _base14_fontname_for_style(style)
    font_obj = _get_base14_font(style)

    fontsize = float(op["fontsize"])
    descender = float(style.get("descender") or -0.2)
    baseline_y = line_rect.y1 + (descender * fontsize)
    baseline_y = min(
        max(baseline_y, line_rect.y0 + (fontsize * 0.65)),
        line_rect.y1 - 0.1,
    )

    text_width = font_obj.text_length(op["text"], fontsize=fontsize)
    x_start = render.x0 + max((render.width - text_width) / 2.0, 0.0)

    try:
        page.insert_text(
            (x_start, baseline_y),
            op["text"],
            fontname=base14_name,
            fontsize=fontsize,
            color=op["text_color"],
            overlay=True,
        )
        return
    except Exception as exc:
        logger.debug("insert_text failed for '%s': %s", op["text"], exc)

    try:
        tw = pymupdf.TextWriter(page.rect, color=op["text_color"])
        tw.fill_textbox(
            render,
            op["text"],
            font=font_obj,
            fontsize=fontsize,
            align=op.get("text_align", pymupdf.TEXT_ALIGN_CENTER),
        )
        tw.write_text(page, overlay=True)
        return
    except Exception as exc:
        logger.debug("TextWriter failed for '%s': %s", op["text"], exc)

    try:
        page.insert_textbox(
            render,
            op["text"],
            fontname=base14_name,
            fontsize=fontsize,
            color=op["text_color"],
            align=op.get("text_align", pymupdf.TEXT_ALIGN_CENTER),
            overlay=True,
        )
    except Exception as exc:
        logger.warning(
            "All text insertion methods failed for '%s': %s",
            op["text"],
            exc,
        )


def _add_footer_watermark(doc: pymupdf.Document) -> None:
    for page in doc:
        text_width = pymupdf.get_text_length(
            WATERMARK_TEXT,
            fontname="helv",
            fontsize=8,
        )
        x_pos = max(24.0, page.rect.width - text_width - 24.0)
        y_pos = page.rect.height - 12.0
        page.insert_text(
            (x_pos, y_pos),
            WATERMARK_TEXT,
            fontsize=8,
            fontname="helv",
            color=(0.72, 0.72, 0.72),
        )


@register_anonymizer
class PdfAnonymizer(BaseAnonymizer):
    extension = "pdf"

    def anonymize(
        self,
        item: dict,
        preds: list[dict],
        output_dir: str = ".",
        render_context: dict[str, Any] | None = None,
    ) -> str:
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
            matched_paragraphs = _match_predictions_to_layout(layout_paragraphs, preds)

            _apply_minimal_boundary_merge(matched_paragraphs, render_context)
            page_ops, widget_ops, signature_widget_ops = _collect_page_redactions(
                doc,
                matched_paragraphs,
                render_context,
            )
            _apply_redactions(doc, page_ops, widget_ops, signature_widget_ops)
            _add_footer_watermark(doc)

            os.makedirs(output_dir, exist_ok=True)
            output_path = Path(output_dir) / f"{file_path.stem}.anonymized.pdf"
            doc.save(str(output_path))

        return str(output_path)
