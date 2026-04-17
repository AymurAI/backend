from __future__ import annotations

import re
from copy import deepcopy
from typing import Any
from unicodedata import normalize

import pymupdf
from jiwer import cer

from aymurai.logger import get_logger
from aymurai.text.anonymization.alignment import (
    _label_replacement_end as _label_end,
)
from aymurai.text.anonymization.alignment import (
    _label_replacement_start as _label_start,
)
from aymurai.text.anonymization.alignment import (
    resolve_render_token,
)
from aymurai.text.anonymization.pdf.common import (
    PDF_TAG_RECT_GAP_FACTOR,
    PDF_TAG_RECT_GAP_MAX,
    PDF_TAG_RECT_GAP_MIN,
    _build_flexible_pattern,
    _build_spans_detail,
    _font_size,
    _group_adjacent_rects,
    _line_style,
    _line_text,
    _rect_tuple,
    _rect_vertical_overlap,
)

logger = get_logger(__name__)


def _same_boundary_candidate(left: dict, right: dict) -> bool:
    """
    Checks whether two labels can share a merged boundary token.

    Args:
        left (dict): The left rectangle or label to compare.
        right (dict): The right rectangle or label to compare.

    Returns:
        bool: Whether the labels can share a boundary token.
    """
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
    """
    Resolves the logical replacement token for a label.

    Args:
        label (dict): The label metadata being processed.
        render_context (dict[str, Any] | None): The rendering context used to resolve replacement tokens.

    Returns:
        str: The logical token that should replace the label.
    """
    boundary_token = label.get("_boundary_token")
    if boundary_token:
        return boundary_token

    token = resolve_render_token(label, render_context)
    return token or "ENT"


def _apply_minimal_boundary_merge(
    paragraphs: list[dict],
    render_context: dict[str, Any] | None,
) -> None:
    """
    Propagates a shared token across paragraph-boundary label pairs.

    Args:
        paragraphs (list[dict]): The paragraph collection being processed.
        render_context (dict[str, Any] | None): The rendering context used to resolve replacement tokens.
    """
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
    """
    Builds normalized paragraph metadata from the parsed PDF layout.

    Args:
        parsed_doc (Any): The parsed PDF layout document.

    Returns:
        list[dict]: The normalized layout paragraphs extracted from the parsed document.
    """
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
    """
    Matches model predictions to the closest layout paragraphs.

    Args:
        layout_paragraphs (list[dict]): The `layout_paragraphs` value used by this helper.
        preds (list[dict]): The predictions to apply to the document.

    Returns:
        list[dict]: The predictions annotated with their matched layout metadata.
    """
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


def _pick_rect_group_for_segment(
    page: pymupdf.Page,
    line: dict,
    text: str,
    line_x_cursor: dict[tuple[int, int, int], float],
) -> pymupdf.Rect:
    """
    Chooses the best rectangle group for a text segment on the page.

    Args:
        page (pymupdf.Page): The PDF page being processed.
        line (dict): The parsed line metadata being processed.
        text (str): The text value being normalized or searched.
        line_x_cursor (dict[tuple[int, int, int], float]): The per-line cursor used to keep page searches stable.

    Returns:
        pymupdf.Rect | None: The chosen rectangle group for the segment, if found.
    """
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


def _normalize_line_chars(spans: list[dict]) -> list[dict[str, Any]]:
    """
    Normalizes per-character span data into searchable character entries.

    Args:
        spans (list[dict]): The span collection to normalize into character entries.

    Returns:
        list[dict[str, Any]]: The normalized character entries for the line.
    """
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
    """
    Extracts character-level geometry for a parsed line from the page text.

    Args:
        page (pymupdf.Page): The PDF page being processed.
        line (dict): The parsed line metadata being processed.

    Returns:
        list[dict[str, Any]]: The character entries extracted from the page.
    """
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


def _line_chars_text(chars: list[dict[str, Any]]) -> str:
    """
    Builds the searchable text for a character entry list.

    Args:
        chars (list[dict[str, Any]]): The character entry list being processed.

    Returns:
        str: The concatenated character text.
    """
    return "".join(str(entry.get("char") or "") for entry in chars)


def _find_line_char_span(
    chars: list[dict[str, Any]],
    text: str,
    *,
    start: int = 0,
    raw_text: str | None = None,
) -> tuple[int, int] | None:
    """
    Finds the character span for a text fragment inside a line.

    Args:
        chars (list[dict[str, Any]]): The character entry list being processed.
        text (str): The text value being normalized or searched.
        start (int, optional): The preferred start offset for the search. Defaults to 0.
        raw_text (str | None, optional): The raw line text used as a fallback search surface. Defaults to None.

    Returns:
        tuple[int, int] | None: The start and end character offsets, if found.
    """
    if not chars or not text:
        return None

    haystack = raw_text if raw_text is not None else _line_chars_text(chars)
    pattern = _build_flexible_pattern(text)

    def _search(offset: int) -> tuple[int, int] | None:
        """
        Searches for the candidate span from the provided offset.

        Args:
            offset (int): The search offset used by the nested helper.

        Returns:
            tuple[int, int] | None: The matching span for the current offset, if found.
        """
        exact_idx = haystack.find(text, offset)
        flexible_span = None
        if pattern:
            match = re.search(pattern, haystack[offset:])
            if match is not None:
                flexible_span = (offset + match.start(), offset + match.end())

        if exact_idx < 0:
            return flexible_span
        exact_span = (exact_idx, exact_idx + len(text))
        if flexible_span is None:
            return exact_span
        return min(exact_span, flexible_span, key=lambda span: span[0])

    span = _search(start)
    if span is None and start > 0:
        span = _search(0)
    return span


def _rect_from_char_slice(
    chars: list[dict[str, Any]],
    start: int,
    end: int,
) -> pymupdf.Rect | None:
    """
    Builds a rectangle covering the requested character slice.

    Args:
        chars (list[dict[str, Any]]): The character entry list being processed.
        start (int): The preferred start offset for the search.
        end (int): The `end` value used by this helper.

    Returns:
        pymupdf.Rect | None: The rectangle covering the requested character slice.
    """
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
