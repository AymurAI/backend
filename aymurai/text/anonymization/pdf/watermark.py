from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pymupdf

from aymurai.logger import get_logger
from aymurai.settings import settings

logger = get_logger(__name__)

WATERMARK_PREFIX_TEXT = "Documento anonimizado por "
WATERMARK_LINK_TEXT = "AymurAI"
WATERMARK_TEXT = f"{WATERMARK_PREFIX_TEXT}{WATERMARK_LINK_TEXT}"
WATERMARK_URL = "https://www.aymurai.info/"
WATERMARK_FONT_SIZE = 10.0
WATERMARK_MARGIN_X = 24.0
WATERMARK_BASELINE_MARGIN = 12.0
WATERMARK_TOP_BASELINE = 22.0
WATERMARK_RECT_PADDING_X = 4.0
WATERMARK_RECT_PADDING_Y = 4.0
WATERMARK_COLLISION_PADDING = 12.0
WATERMARK_TEXT_COLOR = tuple(channel / 255 for channel in (192, 192, 192))
WATERMARK_LINK_COLOR = tuple(channel / 255 for channel in (115, 190, 250))


def _candidate_font_paths() -> tuple[list[Path], list[Path]]:
    """
    Builds the ordered list of candidate font paths for the PDF watermark.

    Returns:
        tuple[list[Path], list[Path]]: The regular and bold watermark font candidates.
    """
    override_regular = (
        os.getenv("PDF_WATERMARK_FONT_REGULAR") or settings.PDF_WATERMARK_FONT_REGULAR
    )
    override_bold = (
        os.getenv("PDF_WATERMARK_FONT_BOLD") or settings.PDF_WATERMARK_FONT_BOLD
    )

    regular_candidates: list[Path] = []
    bold_candidates: list[Path] = []

    if override_regular:
        regular_candidates.append(Path(override_regular).expanduser())
    if override_bold:
        bold_candidates.append(Path(override_bold).expanduser())

    resource_roots: list[Path] = []
    resources_base = Path(settings.RESOURCES_BASEPATH)
    if resources_base.is_absolute():
        resource_roots.append(resources_base)
    else:
        resource_roots.append((Path("/workspace") / resources_base).resolve())
        resource_roots.append(resources_base)

    font_roots: list[Path] = []
    for root in resource_roots:
        font_roots.extend([root / "fonts", root / "fonts" / "archivo"])

    for root in font_roots:
        regular_candidates.extend(
            [
                root / "Archivo-Regular.ttf",
                root / "Archivo-Regular.otf",
                root / "Archivo[wdth,wght].ttf",
                root / "Archivo-VariableFont_wdth,wght.ttf",
            ]
        )
        bold_candidates.extend(
            [
                root / "Archivo-Bold.ttf",
                root / "Archivo-Bold.otf",
                root / "Archivo-BoldItalic.ttf",
                root / "Archivo-VariableFont_wdth,wght.ttf",
                root / "Archivo[wdth,wght].ttf",
            ]
        )

    system_roots = [
        Path("/usr/share/fonts/truetype/archivo"),
        Path("/usr/share/fonts/opentype/archivo"),
        Path("/usr/local/share/fonts/archivo"),
        Path.home() / ".local/share/fonts",
        Path.home() / ".local/share/fonts/archivo",
    ]
    for root in system_roots:
        regular_candidates.extend(
            [
                root / "Archivo-Regular.ttf",
                root / "Archivo-Regular.otf",
                root / "Archivo[wdth,wght].ttf",
                root / "Archivo-VariableFont_wdth,wght.ttf",
            ]
        )
        bold_candidates.extend(
            [
                root / "Archivo-Bold.ttf",
                root / "Archivo-Bold.otf",
                root / "Archivo-BoldItalic.ttf",
                root / "Archivo-VariableFont_wdth,wght.ttf",
                root / "Archivo[wdth,wght].ttf",
            ]
        )

    return regular_candidates, bold_candidates


def _first_existing_path(paths: list[Path]) -> str | None:
    """
    Returns the first existing file path from the provided candidates.

    Args:
        paths (list[Path]): The candidate paths to inspect.

    Returns:
        str | None: The first existing file path, if one is found.
    """
    seen: set[str] = set()
    for path in paths:
        expanded = path.expanduser()
        resolved = str(expanded)
        if resolved in seen:
            continue
        seen.add(resolved)
        if expanded.exists() and expanded.is_file():
            return str(expanded)
    return None


@lru_cache(maxsize=1)
def _watermark_font_paths() -> tuple[str | None, str | None]:
    """
    Resolves the font paths used by the PDF watermark.

    Returns:
        tuple[str | None, str | None]: The resolved regular and bold watermark font paths.
    """
    regular_candidates, bold_candidates = _candidate_font_paths()
    regular_path = _first_existing_path(regular_candidates)
    bold_path = _first_existing_path(bold_candidates)
    if regular_path is None and bold_path is not None:
        regular_path = bold_path
    if bold_path is None:
        bold_path = regular_path
    return regular_path, bold_path


@lru_cache(maxsize=1)
def _watermark_font_config() -> dict[str, Any]:
    """
    Builds the font configuration used to render the PDF watermark.

    Returns:
        dict[str, Any]: The watermark font configuration dictionary.
    """
    regular_path, bold_path = _watermark_font_paths()
    if regular_path:
        try:
            return {
                "text_fontname": "archivo-watermark",
                "text_fontfile": regular_path,
                "text_font": pymupdf.Font(fontfile=regular_path),
                "link_fontname": "archivo-watermark-bold",
                "link_fontfile": bold_path or regular_path,
                "link_font": pymupdf.Font(fontfile=bold_path or regular_path),
            }
        except Exception as exc:
            logger.warning(
                "Could not load Archivo font for PDF watermark, falling back to Base-14 fonts: %s",
                exc,
            )

    return {
        "text_fontname": "Helvetica",
        "text_fontfile": None,
        "text_font": pymupdf.Font("Helvetica"),
        "link_fontname": "Helvetica-Bold",
        "link_fontfile": None,
        "link_font": pymupdf.Font("Helvetica-Bold"),
    }


def _watermark_text_length(
    text: str,
    *,
    font_obj: pymupdf.Font,
    fontname: str,
    fontsize: float,
) -> float:
    """
    Measures the rendered width of watermark text.

    Args:
        text (str): The text value being normalized or searched.
        font_obj (pymupdf.Font): The font object used for measurement.
        fontname (str): The font name to use for measurement or rendering.
        fontsize (float): The font size used for measurement or rendering.

    Returns:
        float: The rendered width of the watermark text.
    """
    try:
        return float(font_obj.text_length(text, fontsize=fontsize))
    except Exception:
        return float(
            pymupdf.get_text_length(text, fontname=fontname, fontsize=fontsize)
        )


def _insert_watermark_text(
    page: pymupdf.Page,
    point: tuple[float, float],
    text: str,
    *,
    fontname: str,
    fontsize: float,
    color: tuple[float, float, float],
    fontfile: str | None = None,
) -> None:
    """
    Inserts watermark text onto a page using the resolved font settings.

    Args:
        page (pymupdf.Page): The PDF page being processed.
        point (tuple[float, float]): The insertion point on the page.
        text (str): The text value being normalized or searched.
        fontname (str): The font name to use for measurement or rendering.
        fontsize (float): The font size used for measurement or rendering.
        color (tuple[float, float, float]): The PDF RGB color used to render the text.
        fontfile (str | None, optional): The optional font file path to embed for rendering. Defaults to None.
    """
    kwargs: dict[str, Any] = {
        "fontsize": fontsize,
        "fontname": fontname,
        "color": color,
        "overlay": True,
    }
    if fontfile:
        kwargs["fontfile"] = fontfile
    page.insert_text(point, text, **kwargs)


def _expanded_rect(rect: pymupdf.Rect, padding: float) -> pymupdf.Rect:
    """
    Expands a rectangle by a uniform padding in every direction.

    Args:
        rect (pymupdf.Rect): The rectangle to expand.
        padding (float): The amount of padding to apply on every side.

    Returns:
        pymupdf.Rect: The expanded rectangle.
    """
    return pymupdf.Rect(
        rect.x0 - padding,
        rect.y0 - padding,
        rect.x1 + padding,
        rect.y1 + padding,
    )


def _watermark_corner_order(page_index: int) -> list[str]:
    """
    Builds the preferred watermark corner order for a page.

    Args:
        page_index (int): The page index being processed.

    Returns:
        list[str]: The ordered watermark corner candidates for the page.
    """
    if page_index % 2 == 0:
        return ["bottom-right", "bottom-left", "top-left", "top-right"]
    return ["bottom-left", "top-left", "top-right", "bottom-right"]


def _watermark_layout_for_corner(
    page: pymupdf.Page,
    corner: str,
    *,
    prefix_width: float,
    link_width: float,
    total_width: float,
) -> dict[str, Any]:
    """
    Builds the watermark geometry for a specific page corner.

    Args:
        page (pymupdf.Page): The PDF page being processed.
        corner (str): The corner identifier used to position the watermark.
        prefix_width (float): The rendered width of the watermark prefix text.
        link_width (float): The rendered width of the watermark link text.
        total_width (float): The total rendered width of the watermark text.

    Returns:
        dict[str, Any]: The watermark layout data for the corner.
    """
    if corner.endswith("right"):
        x_start = max(
            WATERMARK_MARGIN_X,
            page.rect.width - total_width - WATERMARK_MARGIN_X,
        )
    else:
        x_start = WATERMARK_MARGIN_X

    if corner.startswith("bottom"):
        baseline_y = page.rect.height - WATERMARK_BASELINE_MARGIN
    else:
        baseline_y = WATERMARK_TOP_BASELINE

    link_x = x_start + prefix_width
    text_top = baseline_y - WATERMARK_FONT_SIZE
    banner_rect = pymupdf.Rect(
        x_start - WATERMARK_RECT_PADDING_X,
        text_top - WATERMARK_RECT_PADDING_Y,
        x_start + total_width + WATERMARK_RECT_PADDING_X,
        baseline_y + WATERMARK_RECT_PADDING_Y,
    )
    link_rect = pymupdf.Rect(
        link_x,
        text_top,
        link_x + link_width,
        baseline_y + 2.0,
    )

    return {
        "corner": corner,
        "x_start": x_start,
        "baseline_y": baseline_y,
        "link_x": link_x,
        "banner_rect": banner_rect,
        "link_rect": link_rect,
    }


def _occupied_page_rects(page: pymupdf.Page) -> list[pymupdf.Rect]:
    """
    Collects page rectangles already occupied by visible content.

    Args:
        page (pymupdf.Page): The PDF page being processed.

    Returns:
        list[pymupdf.Rect]: The occupied rectangles found on the page.
    """
    occupied: list[pymupdf.Rect] = []

    text_data = page.get_text("dict")
    for block in text_data.get("blocks", []):
        bbox = block.get("bbox")
        if bbox is None:
            continue
        rect = pymupdf.Rect(bbox)
        if rect.get_area() <= 0:
            continue
        occupied.append(_expanded_rect(rect, WATERMARK_COLLISION_PADDING))

    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None:
            continue
        rect = pymupdf.Rect(rect)
        if rect.get_area() <= 0:
            continue
        occupied.append(_expanded_rect(rect, WATERMARK_COLLISION_PADDING))

    return occupied


def _watermark_overlap_score(
    banner_rect: pymupdf.Rect,
    occupied_rects: list[pymupdf.Rect],
) -> tuple[float, float, int]:
    """
    Scores a watermark placement by the amount of page content it overlaps.

    Args:
        banner_rect (pymupdf.Rect): The watermark banner rectangle being scored.
        occupied_rects (list[pymupdf.Rect]): The occupied page rectangles used for overlap checks.

    Returns:
        tuple[float, float, int]: The overlap ratio, overlap area, and overlap count for the placement.
    """
    overlap_area = 0.0
    overlap_count = 0
    banner_area = max(banner_rect.get_area(), 1.0)

    for rect in occupied_rects:
        if not banner_rect.intersects(rect):
            continue
        intersection = banner_rect & rect
        area = intersection.get_area()
        if area <= 0:
            continue
        overlap_area += area
        overlap_count += 1

    return overlap_area / banner_area, overlap_area, overlap_count


def _choose_watermark_layout(
    page: pymupdf.Page,
    page_index: int,
    *,
    prefix_width: float,
    link_width: float,
    total_width: float,
) -> dict[str, Any]:
    """
    Selects the watermark placement with the least overlap on a page.

    Args:
        page (pymupdf.Page): The PDF page being processed.
        page_index (int): The page index being processed.
        prefix_width (float): The rendered width of the watermark prefix text.
        link_width (float): The rendered width of the watermark link text.
        total_width (float): The total rendered width of the watermark text.

    Returns:
        dict[str, Any]: The chosen watermark layout data.
    """
    occupied_rects = _occupied_page_rects(page)
    candidate_layouts = [
        _watermark_layout_for_corner(
            page,
            corner,
            prefix_width=prefix_width,
            link_width=link_width,
            total_width=total_width,
        )
        for corner in _watermark_corner_order(page_index)
    ]

    best_layout = candidate_layouts[0]
    best_score: tuple[float, float, int] | None = None

    for layout in candidate_layouts:
        score = _watermark_overlap_score(layout["banner_rect"], occupied_rects)
        if score[0] == 0.0 and score[1] == 0.0:
            return layout
        if best_score is None or score < best_score:
            best_layout = layout
            best_score = score

    return best_layout


def add_pdf_footer_watermark(doc: pymupdf.Document) -> None:
    """
    Adds the anonymization watermark to the least crowded corner of each PDF page.

    Args:
        doc (pymupdf.Document): The PDF document being processed.
    """
    font_config = _watermark_font_config()
    prefix_width = _watermark_text_length(
        WATERMARK_PREFIX_TEXT,
        font_obj=font_config["text_font"],
        fontname=font_config["text_fontname"],
        fontsize=WATERMARK_FONT_SIZE,
    )
    link_width = _watermark_text_length(
        WATERMARK_LINK_TEXT,
        font_obj=font_config["link_font"],
        fontname=font_config["link_fontname"],
        fontsize=WATERMARK_FONT_SIZE,
    )
    total_width = prefix_width + link_width

    for page_index, page in enumerate(doc):
        layout = _choose_watermark_layout(
            page,
            page_index,
            prefix_width=prefix_width,
            link_width=link_width,
            total_width=total_width,
        )
        baseline_y = layout["baseline_y"]
        x_start = layout["x_start"]
        link_x = layout["link_x"]

        _insert_watermark_text(
            page,
            (x_start, baseline_y),
            WATERMARK_PREFIX_TEXT,
            fontname=font_config["text_fontname"],
            fontsize=WATERMARK_FONT_SIZE,
            color=WATERMARK_TEXT_COLOR,
            fontfile=font_config["text_fontfile"],
        )
        _insert_watermark_text(
            page,
            (link_x, baseline_y),
            WATERMARK_LINK_TEXT,
            fontname=font_config["link_fontname"],
            fontsize=WATERMARK_FONT_SIZE,
            color=WATERMARK_LINK_COLOR,
            fontfile=font_config["link_fontfile"],
        )

        if layout["corner"].startswith("bottom"):
            underline_y = min(page.rect.height - 1.0, baseline_y + 1.0)
        else:
            underline_y = baseline_y + 1.0
        page.draw_line(
            (link_x, underline_y),
            (link_x + link_width, underline_y),
            color=WATERMARK_LINK_COLOR,
            width=0.8,
            overlay=True,
        )
        page.insert_link(
            {
                "kind": pymupdf.LINK_URI,
                "from": layout["link_rect"],
                "uri": WATERMARK_URL,
            }
        )
