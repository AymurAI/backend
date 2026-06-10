from __future__ import annotations

import re
from functools import lru_cache
from typing import Any
from unicodedata import normalize

import pymupdf

TEXT_FLAG_ITALIC = 2
TEXT_FLAG_SERIF = 4
TEXT_FLAG_MONOSPACED = 8
TEXT_FLAG_BOLD = 16
PDF_TAG_MIN_FONT_SIZE = 7.0
PDF_TAG_FONT_STEP = 0.5
PDF_TAG_MAX_ABBREVIATION = 3
PDF_TOKEN_ALIAS_MAP: dict[str, tuple[str, ...]] = {
    "CORREO_ELECTRONICO": ("CORREO", "MAIL"),
    "CUIT_CUIL": ("CUIT", "CUIL"),
    "DIRECCION": ("DIR",),
    "ESTUDIOS": ("EDU",),
    "MARCA_AUTOMOVIL": ("VEHICULO", "AUTO"),
    "NACIONALIDAD": ("PAIS", "NAC"),
    "NOMBRE_ARCHIVO": ("ARCHIVO", "FILE"),
    "NUM_ACTUACION": ("ACTUACION", "ACT"),
    "NUM_CAJA_AHORRO": ("CAJA_AHORRO", "CAJA"),
    "NUM_EXPEDIENTE": ("EXPEDIENTE", "EXPTE"),
    "NUM_MATRICULA": ("MATRICULA", "MAT"),
    "PATENTE_DOMINIO": ("PATENTE", "DOMINIO"),
    "TELEFONO": ("TEL",),
    "TEXTO_ANONIMIZAR": ("ANONIMIZAR", "TEXTO"),
    "USUARIX": ("USER",),
}
PDF_TAG_RECT_X_PADDING = 0.5
PDF_TAG_RECT_Y_PADDING = 0.0
PDF_TAG_RECT_INSET = 0.5
PDF_TAG_RECT_GAP_FACTOR = 0.5
PDF_TAG_RECT_GAP_MIN = 3.0
PDF_TAG_RECT_GAP_MAX = 8.0


def _line_text(line: dict) -> str:
    """
    Builds the plain text content for a parsed PDF line.

    Args:
        line (dict): The parsed line metadata being processed.

    Returns:
        str: The concatenated text content for the line.
    """
    return "".join(span.get("text", "") for span in line.get("spans", []))


def _rect_tuple(value: Any) -> tuple[float, float, float, float]:
    """
    Normalizes a rectangle-like value into a coordinate tuple.

    Args:
        value (Any): The rectangle-like value to normalize.

    Returns:
        tuple[float, float, float, float]: The normalized rectangle coordinates.
    """
    if isinstance(value, pymupdf.Rect):
        return (float(value.x0), float(value.y0), float(value.x1), float(value.y1))
    if isinstance(value, (list, tuple)) and len(value) == 4:
        return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
    raise ValueError(f"Invalid rectangle value: {value}")


def _default_style(fallback_size: float = 10.0) -> dict[str, Any]:
    """
    Builds a default text style dictionary for PDF rendering helpers.

    Args:
        fallback_size (float, optional): The fallback font size used when no style data is available. Defaults to 10.0.

    Returns:
        dict[str, Any]: The default style dictionary.
    """
    return {
        "font": "",
        "flags": 0,
        "color": (0.0, 0.0, 0.0),
        "size": fallback_size,
        "ascender": 0.8,
        "descender": -0.2,
    }


def _span_text_weight(span: dict) -> tuple[int, float]:
    """
    Computes a sorting weight for a span based on text length and size.

    Args:
        span (dict): The span metadata being evaluated.

    Returns:
        tuple[int, float]: The text-length and size weight for the span.
    """
    text = str(span.get("text") or "").strip()
    return (len(text), float(span.get("size") or 0.0))


def _pdf_color_from_span(span: dict) -> tuple[float, float, float]:
    """
    Converts a span color value into PDF RGB components.

    Args:
        span (dict): The span metadata being evaluated.

    Returns:
        tuple[float, float, float]: The PDF RGB color components for the span.
    """
    try:
        return tuple(
            float(value) for value in pymupdf.sRGB_to_pdf(int(span.get("color") or 0))
        )
    except Exception:
        return (0.0, 0.0, 0.0)


def _line_style(line: dict, fallback_size: float = 10.0) -> dict[str, Any]:
    """
    Determines the dominant text style for a parsed PDF line.

    Args:
        line (dict): The parsed line metadata being processed.
        fallback_size (float, optional): The fallback font size used when no style data is available. Defaults to 10.0.

    Returns:
        dict[str, Any]: The dominant style dictionary for the line.
    """
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
    """
    Builds per-span style metadata and character offsets for a line.

    Args:
        line (dict): The parsed line metadata being processed.

    Returns:
        tuple[list[dict], int]: The span detail list and left-strip offset.
    """
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
    """
    Resolves the style for the entity offset inside a line entry.

    Args:
        line_entry (dict): The `line_entry` value used by this helper.
        offset_in_stripped_text (int): The entity offset inside the stripped line text.

    Returns:
        dict[str, Any]: The resolved style dictionary for the entity offset.
    """
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
    """
    Calculates a representative font size for a parsed line.

    Args:
        line (dict): The parsed line metadata being processed.
        fallback (float, optional): The fallback font size to use when the line has no span sizes. Defaults to 10.0.

    Returns:
        float: The representative font size for the line.
    """
    spans = line.get("spans") or []
    sizes = [float(span.get("size")) for span in spans if span.get("size")]
    if not sizes:
        return fallback
    size = sum(sizes) / len(sizes)
    return max(size * 0.9, PDF_TAG_MIN_FONT_SIZE)


def _style_flags(style: dict[str, Any]) -> tuple[bool, bool, bool, bool]:
    """
    Extracts boolean style flags from a style dictionary.

    Args:
        style (dict[str, Any]): The style dictionary being analyzed.

    Returns:
        tuple[bool, bool, bool, bool]: The bold, italic, monospace, and serif flags.
    """
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
    """
    Maps a style dictionary to the closest Base-14 font name.

    Args:
        style (dict[str, Any]): The style dictionary being analyzed.

    Returns:
        str: The Base-14 font name that best matches the style.
    """
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
    """
    Builds a whitespace-tolerant regex pattern for the given text.

    Args:
        text (str): The text value being normalized or searched.

    Returns:
        str: The whitespace-tolerant regex pattern.
    """
    tokens = [re.escape(tok) for tok in re.split(r"\s+", text.strip()) if tok]
    return r"\s+".join(tokens)


def _find_flexible(
    haystack: str,
    needle: str,
    start: int = 0,
) -> tuple[int, int] | None:
    """
    Finds a text span using exact and whitespace-tolerant matching.

    Args:
        haystack (str): The source text to search within.
        needle (str): The target text to search for.
        start (int, optional): The preferred start offset for the search. Defaults to 0.

    Returns:
        tuple[int, int] | None: The start and end offsets of the match, if found.
    """
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


def _token_parts(token: str) -> tuple[str, str | None]:
    """
    Splits a logical token into its base label and numeric suffix.

    Args:
        token (str): The logical replacement token being processed.

    Returns:
        tuple[str, str | None]: The token base and optional numeric suffix.
    """
    match = re.match(r"^(.*?)(?:_(\d+))?$", token)
    if not match:
        normalized = token.strip() or "ENT"
        return normalized, None

    base = match.group(1).strip() or "ENT"
    suffix = match.group(2)
    return base, suffix


def _abbreviate_token(base: str, length: int) -> str:
    """
    Builds an abbreviated token label with the requested length.

    Args:
        base (str): The token base label to abbreviate or alias.
        length (int): The target abbreviation length.

    Returns:
        str: The abbreviated token label.
    """
    normalized = "".join(char for char in base.upper() if char.isalnum())
    if not normalized:
        normalized = "ENT"
    return normalized[:length] or normalized[:1] or "E"


def _token_aliases(base: str) -> tuple[str, ...]:
    """
    Returns configured alias labels for a token base.

    Args:
        base (str): The token base label to abbreviate or alias.

    Returns:
        tuple[str, ...]: The configured aliases for the token base.
    """
    aliases = PDF_TOKEN_ALIAS_MAP.get(base.upper(), ())
    normalized_aliases: list[str] = []

    for alias in aliases:
        normalized = re.sub(r"[^A-Z0-9_]", "", str(alias).upper())
        if (
            normalized
            and normalized != base.upper()
            and normalized not in normalized_aliases
        ):
            normalized_aliases.append(normalized)

    return tuple(normalized_aliases)


def _build_display_token_candidates(token: str) -> list[str]:
    """
    Builds the list of token display candidates to try when rendering.

    Args:
        token (str): The logical replacement token being processed.

    Returns:
        list[str]: The candidate display tokens to try when rendering.
    """
    base, suffix = _token_parts(token.upper())
    candidates: list[str] = []

    def add(value: str) -> None:
        """
        Appends a token display candidate when it has not been added yet.

        Args:
            value (str): The rectangle-like value to normalize.
        """
        if value and value not in candidates:
            candidates.append(value)

    def add_base_variants(label: str) -> None:
        """
        Appends the base token variants for the current label candidate.

        Args:
            label (str): The label metadata being processed.
        """
        if suffix:
            add(f"<{label}_{suffix}>")
        add(f"<{label}>")

    add_base_variants(base)

    for alias in _token_aliases(base):
        add_base_variants(alias)

    abbreviated = _abbreviate_token(base, PDF_TAG_MAX_ABBREVIATION)
    add_base_variants(abbreviated)

    return candidates


def _iter_font_sizes(start_size: float) -> list[float]:
    """
    Builds the descending font sizes to try when fitting a token.

    Args:
        start_size (float): The `start_size` value used by this helper.

    Returns:
        list[float]: The font sizes to try in descending order.
    """
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
    """
    Finds a token rendering variant and font size that fit inside a rectangle.

    Args:
        token (str): The logical replacement token being processed.
        rect (pymupdf.Rect): The rectangle used by the helper.
        fontname (str): The font name to use for measurement or rendering.
        base_font_size (float): The initial font size to try when fitting text.
        font_obj (pymupdf.Font | None, optional): The font object used for measurement. Defaults to None.

    Returns:
        tuple[str | None, float | None]: The fitted token text and font size.
    """
    if rect.width <= 0 or rect.height <= 0:
        return None, None

    available_width = max(rect.width - (2 * PDF_TAG_RECT_INSET), 1.0)
    start_size = min(base_font_size, max(rect.height - 1.0, 1.0))
    if start_size < 1.0:
        return None, None

    def _measure(text: str, size: float) -> float:
        """
        Measures the width of a candidate token at the given font size.

        Args:
            text (str): The text value being normalized or searched.
            size (float): The font size used for the current measurement.

        Returns:
            float: The measured width of the candidate text.
        """
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


_BASE14_FONT_CACHE: dict[str, pymupdf.Font] = {}


@lru_cache(maxsize=None)
def _cached_base14_font(name: str) -> pymupdf.Font:
    """
    Loads and caches a Base-14 font by name.

    Args:
        name (str): The Base-14 font name to load.

    Returns:
        pymupdf.Font: The cached Base-14 font object.
    """
    return pymupdf.Font(name)


def _get_base14_font(style: dict[str, Any]) -> pymupdf.Font:
    """
    Returns the cached Base-14 font object for a style dictionary.

    Args:
        style (dict[str, Any]): The style dictionary being analyzed.

    Returns:
        pymupdf.Font: The cached Base-14 font for the style.
    """
    name = _base14_fontname_for_style(style)
    font = _BASE14_FONT_CACHE.get(name)
    if font is None:
        font = _cached_base14_font(name)
        _BASE14_FONT_CACHE[name] = font
    return font


def _rect_vertical_overlap(left: pymupdf.Rect, right: pymupdf.Rect) -> float:
    """
    Calculates the vertical overlap ratio between two rectangles.

    Args:
        left (pymupdf.Rect): The left rectangle or label to compare.
        right (pymupdf.Rect): The right rectangle or label to compare.

    Returns:
        float: The vertical overlap ratio between the rectangles.
    """
    overlap = max(0.0, min(left.y1, right.y1) - max(left.y0, right.y0))
    min_height = max(min(left.height, right.height), 1e-6)
    return overlap / min_height


def _group_adjacent_rects(
    rects: list[pymupdf.Rect], max_gap: float
) -> list[pymupdf.Rect]:
    """
    Merges horizontally adjacent rectangles that belong to the same segment.

    Args:
        rects (list[pymupdf.Rect]): The `rects` value used by this helper.
        max_gap (float): The `max_gap` value used by this helper.

    Returns:
        list[pymupdf.Rect]: The merged rectangle groups.
    """
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
