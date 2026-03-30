from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from unicodedata import normalize

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
PDF_TAG_RECT_X_PADDING = 2.0
PDF_TAG_RECT_Y_PADDING = 0.75
PDF_TAG_RECT_INSET = 0.5
PDF_TAG_RECT_GAP_FACTOR = 0.5
PDF_TAG_RECT_GAP_MIN = 3.0
PDF_TAG_RECT_GAP_MAX = 8.0

# Vertical overlap ratio required to consider two image rects as matching
_IMAGE_OVERLAP_THRESHOLD = 0.3


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


class _FontCache:
    """Extracts and caches original fonts from the PDF so replacement text
    preserves the exact original typeface whenever possible.

    Fonts are embedded into each page on first use via ``insert_font`` so that
    ``insert_textbox`` / ``insert_text`` can reference them by name.
    """

    def __init__(self, doc: pymupdf.Document) -> None:
        self._doc = doc
        # font_name -> font buffer (bytes)
        self._buffers: dict[str, bytes] = {}
        # font_name -> registered insertion name for insert_text/insert_textbox
        self._registered: dict[str, str] = {}
        # page_index -> set of already-inserted font names
        self._page_fonts: dict[int, set[str]] = {}

        self._extract_all_fonts()

    # ------------------------------------------------------------------
    def _extract_all_fonts(self) -> None:
        """Walk every page and extract font buffers by xref."""
        seen_xrefs: set[int] = set()
        for page_idx in range(len(self._doc)):
            for font_entry in self._doc.get_page_fonts(page_idx, full=True):
                xref = font_entry[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                name, ext, _ftype, content = self._doc.extract_font(xref)
                if not content or not name:
                    continue
                # Normalise name (some fonts carry subset prefixes like ABCDEF+)
                clean = name.split("+")[-1] if "+" in name else name
                if clean not in self._buffers:
                    self._buffers[clean] = content
                    logger.debug(
                        "FontCache: extracted '%s' (%d bytes)", clean, len(content)
                    )

    # ------------------------------------------------------------------
    def resolve(self, style: dict[str, Any], page: pymupdf.Page) -> str:
        """Return the best font name to use for *style* on *page*.

        If the original font can be recovered from the document it is
        re-embedded into the page and its name is returned.  Otherwise a
        Base-14 fallback is returned.
        """
        original_font = str(style.get("font") or "")
        # Strip subset prefix (e.g. BCDEEE+ArialMT -> ArialMT)
        clean = original_font.split("+")[-1] if "+" in original_font else original_font

        if clean and clean in self._buffers:
            return self._ensure_on_page(clean, page)

        # Try a looser match (case-insensitive, ignoring commas, hyphens, spaces)
        normalised = self._normalise_key(clean)
        if normalised:
            # Exact normalised match
            for cached_name in self._buffers:
                if self._normalise_key(cached_name) == normalised:
                    return self._ensure_on_page(cached_name, page)

            # Prefix / contains match (e.g. span says "LiberationSansNarrow"
            # but cached name is "Liberation Sans Narrow Regular")
            for cached_name in self._buffers:
                cached_norm = self._normalise_key(cached_name)
                if cached_norm.startswith(normalised) or normalised.startswith(
                    cached_norm
                ):
                    return self._ensure_on_page(cached_name, page)

        # Fallback to Base-14
        return _base14_fontname_for_style(style)

    # ------------------------------------------------------------------
    def _ensure_on_page(self, font_name: str, page: pymupdf.Page) -> str:
        """Register the font on *page* if not already done."""
        page_idx = page.number
        if page_idx not in self._page_fonts:
            self._page_fonts[page_idx] = set()

        # Derive a short insertion name from the font (must start with /)
        insert_name = self._registered.get(font_name)
        if insert_name is None:
            # sanitise: keep only alnum
            safe = re.sub(r"[^A-Za-z0-9]", "", font_name)[:20] or "CustomFont"
            insert_name = f"F_{safe}"
            self._registered[font_name] = insert_name

        if font_name not in self._page_fonts[page_idx]:
            try:
                page.insert_font(
                    fontname=insert_name,
                    fontbuffer=self._buffers[font_name],
                )
            except Exception as exc:
                logger.debug("FontCache: could not insert '%s': %s", font_name, exc)
                return _base14_fontname_for_style({"font": font_name})
            self._page_fonts[page_idx].add(font_name)

        return insert_name

    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_key(name: str) -> str:
        return re.sub(r"[\-,_ ]", "", name).lower()


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
    alt_text = attrs.get("aymurai_alt_text")
    if alt_text:
        return str(alt_text)

    start = _label_start(label)
    end = _label_end(label)
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


def _make_font_obj(
    font_cache: _FontCache | None, style: dict[str, Any]
) -> pymupdf.Font | None:
    """Try to build a ``pymupdf.Font`` from the cached buffer for accurate
    text measurement.  Returns ``None`` on failure."""
    if font_cache is None:
        return None
    original_font = str(style.get("font") or "")
    clean = original_font.split("+")[-1] if "+" in original_font else original_font
    buf = font_cache._buffers.get(clean)
    if not buf:
        # Try normalised / prefix lookup
        norm = _FontCache._normalise_key(clean)
        if norm:
            for cached_name, cached_buf in font_cache._buffers.items():
                cached_norm = _FontCache._normalise_key(cached_name)
                if (
                    cached_norm == norm
                    or cached_norm.startswith(norm)
                    or norm.startswith(cached_norm)
                ):
                    buf = cached_buf
                    break
    if buf:
        try:
            return pymupdf.Font(fontbuffer=buf)
        except Exception:
            pass
    return None


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
    pad_x = min(PDF_TAG_RECT_X_PADDING, max(rect.height * 0.2, 0.5))
    pad_y = min(PDF_TAG_RECT_Y_PADDING, max(rect.height * 0.08, 0.25))
    padded.x0 = max(clip.x0, padded.x0 - pad_x)
    padded.y0 = max(clip.y0, padded.y0 - pad_y)
    padded.x1 = min(clip.x1, padded.x1 + pad_x)
    padded.y1 = min(clip.y1, padded.y1 + pad_y)
    return padded


def _render_rect(rect: pymupdf.Rect) -> pymupdf.Rect:
    render_rect = pymupdf.Rect(rect)
    inset = min(PDF_TAG_RECT_INSET, max(render_rect.height * 0.1, 0.0))
    render_rect.x0 += inset
    render_rect.x1 -= inset
    if render_rect.x1 <= render_rect.x0:
        render_rect = pymupdf.Rect(rect)
    return render_rect


def _build_page_op(
    rect: pymupdf.Rect,
    line: dict | None,
    token: str,
    page: pymupdf.Page | None = None,
    font_cache: _FontCache | None = None,
    is_image: bool = False,
) -> dict[str, Any]:
    line_clip = pymupdf.Rect(line["bbox"]) if line else pymupdf.Rect(rect)
    canvas_rect = _padded_rect(rect, line_clip)
    render_rect = _render_rect(canvas_rect)
    style = (line or {}).get("style") or _default_style()
    base_font_size = float((line or {}).get("font_size") or style.get("size") or 10.0)

    # Resolve font: prefer original font from cache, fallback to Base-14
    if font_cache is not None and page is not None:
        fontname = font_cache.resolve(style, page)
    else:
        fontname = _base14_fontname_for_style(style)

    font_obj = _make_font_obj(font_cache, style)

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
        "redact_rect": canvas_rect,
        "canvas_rect": canvas_rect,
        "render_rect": render_rect,
        "text": display_token,
        "logical_token": token,
        "fontname": fontname,
        "fontsize": fitted_size,
        "text_color": style.get("color") or (0.0, 0.0, 0.0),
        "is_image": is_image,
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


def _collect_page_redactions(
    doc: pymupdf.Document,
    paragraphs: list[dict],
    render_context: dict[str, Any] | None,
    font_cache: _FontCache | None = None,
) -> dict[int, list[dict]]:
    page_ops: dict[int, list[dict]] = {}
    line_x_cursor: dict[tuple[int, int, int], float] = {}

    # Pre-compute image rects per page
    page_image_rects: dict[int, list[pymupdf.Rect]] = {}

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

        # Lazy-load image rects for this page
        if page_index not in page_image_rects:
            page_image_rects[page_index] = _image_rects_for_clip(page, page.rect)

        for label in labels:
            entity_text = _label_surface_text(label, document).strip()
            if not entity_text:
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
                            page=page,
                            font_cache=font_cache,
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
                            page=page,
                            font_cache=font_cache,
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
            segments: list[tuple[dict, str, pymupdf.Rect]] = []
            for line in lines:
                overlap_start = max(span[0], line["start"])
                overlap_end = min(span[1], line["end"])
                if overlap_end <= overlap_start:
                    continue

                segment_text = line_text[overlap_start:overlap_end].strip()
                if not segment_text:
                    continue

                rect = _pick_rect_group_for_segment(
                    page, line, segment_text, line_x_cursor
                )

                # Check for image overlap
                img_rect = _entity_overlaps_image(
                    page,
                    rect,
                    page_image_rects[page_index],
                )
                segments.append((line, segment_text, rect, img_rect))

            if not segments:
                continue

            if len(segments) == 1:
                # Single-line entity: write the full token
                line, _seg_text, rect, img_rect = segments[0]
                op = _build_page_op(
                    rect,
                    line,
                    token,
                    page=page,
                    font_cache=font_cache,
                    is_image=(img_rect is not None),
                )
                if img_rect is not None:
                    op["image_rect"] = img_rect
                page_ops.setdefault(page_index, []).append(op)
            else:
                # Multi-line entity: write the token centered on the
                # WIDEST segment only; blank the other segments.
                widest_idx = max(
                    range(len(segments)),
                    key=lambda i: segments[i][2].width,
                )
                any_image = any(seg[3] is not None for seg in segments)

                for seg_idx, (seg_line, _seg_text, seg_rect, seg_img) in enumerate(
                    segments
                ):
                    if seg_idx == widest_idx:
                        # Primary segment: render the token here
                        op = _build_page_op(
                            seg_rect,
                            seg_line,
                            token,
                            page=page,
                            font_cache=font_cache,
                            is_image=any_image,
                        )
                        if seg_img is not None:
                            op["image_rect"] = seg_img
                    else:
                        # Secondary segment: just blank it (no text)
                        op = _build_page_op(
                            seg_rect,
                            seg_line,
                            token,
                            page=page,
                            font_cache=font_cache,
                            is_image=(seg_img is not None),
                        )
                        op["text"] = None  # suppress text rendering
                        op["fontsize"] = None
                        if seg_img is not None:
                            op["image_rect"] = seg_img

                    page_ops.setdefault(page_index, []).append(op)

    return page_ops


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
    font_cache: _FontCache | None = None,
) -> None:
    for page_idx, ops in page_ops.items():
        page = doc[page_idx]

        # 1) Add text redaction annotations (non-image ops only).
        #    Image entities are handled separately with white-rect overlay
        #    to avoid PDF_REDACT_IMAGE_REMOVE which destroys ALL images on
        #    the page.
        for op in ops:
            if not op.get("is_image"):
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

        # 3) Draw white canvas + centered replacement text
        for op in ops:
            is_image = op.get("is_image", False)

            if is_image:
                # For image entities, paint a white rect that covers the
                # FULL image bounding box (not just the entity text rect)
                # so the original content is completely hidden.
                img_rect = op.get("image_rect")
                if img_rect is not None:
                    page.draw_rect(
                        img_rect,
                        color=(1, 1, 1),
                        fill=(1, 1, 1),
                        width=0,
                        overlay=True,
                    )

            # Always white-out the canvas area (text or image)
            canvas = op["canvas_rect"]
            page.draw_rect(
                canvas,
                color=(1, 1, 1),
                fill=(1, 1, 1),
                width=0,
                overlay=True,
            )

            if not op.get("text") or not op.get("fontsize"):
                continue

            render = op["render_rect"]
            style = op.get("style") or {}

            # --- Text insertion strategy ---
            # ``page.insert_textbox`` / ``insert_text`` do NOT support fonts
            # registered via ``page.insert_font`` — they only understand
            # Base-14 names or ``fontfile`` paths.  We therefore use
            # ``TextWriter.fill_textbox`` which accepts a ``pymupdf.Font``
            # object built directly from the cached buffer, giving us both
            # correct typeface and native center alignment.

            written = False

            # Attempt 1: TextWriter with original font buffer
            if font_cache is not None and not written:
                font_obj = _make_font_obj(font_cache, style)
                if font_obj is not None:
                    try:
                        tw = pymupdf.TextWriter(page.rect, color=op["text_color"])
                        tw.fill_textbox(
                            render,
                            op["text"],
                            font=font_obj,
                            fontsize=op["fontsize"],
                            align=pymupdf.TEXT_ALIGN_CENTER,
                        )
                        tw.write_text(page, overlay=True)
                        written = True
                    except Exception as exc:
                        logger.debug(
                            "TextWriter failed for '%s': %s",
                            op["text"],
                            exc,
                        )

            # Attempt 2: insert_textbox with Base-14 fallback font
            if not written:
                base14 = _base14_fontname_for_style(style)
                try:
                    page.insert_textbox(
                        render,
                        op["text"],
                        fontname=base14,
                        fontsize=op["fontsize"],
                        color=op["text_color"],
                        align=pymupdf.TEXT_ALIGN_CENTER,
                        overlay=True,
                    )
                    written = True
                except Exception as exc:
                    logger.debug(
                        "insert_textbox (Base-14) failed for '%s': %s",
                        op["text"],
                        exc,
                    )

            # Attempt 3: insert_text centered with Base-14
            if not written:
                base14 = _base14_fontname_for_style(style)
                try:
                    descender = 0.2
                    baseline_y = render.y1 - (descender * op["fontsize"])
                    baseline_y = min(
                        max(baseline_y, render.y0 + 1.0),
                        render.y1 - 0.25,
                    )
                    text_w = pymupdf.get_text_length(
                        op["text"],
                        fontname=base14,
                        fontsize=op["fontsize"],
                    )
                    x_start = render.x0 + max((render.width - text_w) / 2.0, 0.0)
                    page.insert_text(
                        (x_start, baseline_y),
                        op["text"],
                        fontname=base14,
                        fontsize=op["fontsize"],
                        color=op["text_color"],
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

            # Build font cache to preserve original typefaces
            font_cache = _FontCache(doc)

            layout_paragraphs = _build_layout_paragraphs(parsed_doc)
            matched_paragraphs = _match_predictions_to_layout(layout_paragraphs, preds)

            _apply_minimal_boundary_merge(matched_paragraphs, render_context)
            page_ops = _collect_page_redactions(
                doc,
                matched_paragraphs,
                render_context,
                font_cache=font_cache,
            )
            _apply_redactions(doc, page_ops, font_cache=font_cache)
            _add_footer_watermark(doc)

            os.makedirs(output_dir, exist_ok=True)
            output_path = Path(output_dir) / f"{file_path.stem}.anonymized.pdf"
            doc.save(str(output_path))

        return str(output_path)
