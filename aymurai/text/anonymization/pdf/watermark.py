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


def add_pdf_footer_watermark(doc: pymupdf.Document) -> None:
    """
    Adds the anonymization watermark to the footer of each PDF page.

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
        if page_index % 2 == 0:
            x_start = max(
                WATERMARK_MARGIN_X,
                page.rect.width - total_width - WATERMARK_MARGIN_X,
            )
        else:
            x_start = WATERMARK_MARGIN_X

        baseline_y = page.rect.height - WATERMARK_BASELINE_MARGIN
        link_x = x_start + prefix_width

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

        underline_y = min(page.rect.height - 1.0, baseline_y + 1.0)
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
                "from": pymupdf.Rect(
                    link_x,
                    baseline_y - WATERMARK_FONT_SIZE,
                    link_x + link_width,
                    min(page.rect.height, baseline_y + 2.0),
                ),
                "uri": WATERMARK_URL,
            }
        )
