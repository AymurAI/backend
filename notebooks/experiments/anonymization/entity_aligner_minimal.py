# entity_aligner_minimal.py
from __future__ import annotations

import re
import difflib
import unicodedata
from collections import Counter, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# =========================
# Data structures
# =========================

class AlignmentStatus(Enum):
    MATCH_EXACT = "match_exact"
    MATCH_FUZZY = "match_fuzzy"
    NO_MATCH = None


@dataclass
class CharInterval:
    start_pos: int
    end_pos: int  # exclusive


@dataclass
class Extraction:
    extraction_class: str
    extraction_text: str
    char_interval: Optional[CharInterval]
    alignment_status: AlignmentStatus
    extraction_index: int
    group_index: int = 0
    description: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnnotatedDocument:
    document_id: str
    text: str
    extractions: List[Extraction]


# =========================
# Tokenization & normalization
# =========================

@dataclass
class Token:
    text: str
    start: int
    end: int  # exclusive


# Conserva letras/números y separadores útiles para fechas/IDs
_TOKEN_RE = re.compile(r"\w+|[./:-]")


def _normalize_str(s: str) -> str:
    s = s.lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s.strip())
    return s


def _normalize_token(tok: str) -> str:
    t = _normalize_str(tok)
    # “suavizado” mínimo de bordes y plural muy simple
    t = re.sub(r"^[\W_]+|[\W_]+$", "", t)
    t = re.sub(r"s$", "", t)
    return t


def _tokenize(text: str) -> List[Token]:
    out: List[Token] = []
    for m in _TOKEN_RE.finditer(text):
        out.append(Token(m.group(0), m.start(), m.end()))
    return out


# =========================
# Helpers de límites de palabra / refinado
# =========================

def _snap_to_token_bounds(text: str, start: int, end: int) -> Tuple[int, int]:
    """Ajusta a límites de palabra si el span corta adentro de un alfanumérico."""
    n = len(text)
    s, e = start, end
    while s > 0 and text[s - 1].isalnum():
        s -= 1
    while e < n and text[e].isalnum():
        e += 1
    return s, e


def _refine_boundaries(entity_text: str, source_text: str, s: int, e: int) -> Tuple[int, int]:
    """
    Recorta 1..5 chars a izquierda/derecha si mantiene o mejora similitud
    (evita capturar artículos/comas/espacios de más).
    """
    target = _normalize_str(entity_text)
    best_s, best_e = s, e
    best_score = difflib.SequenceMatcher(
        None, _normalize_str(source_text[s:e]), target, autojunk=False
    ).ratio()

    # Probar mover start → derecha
    for shift in range(1, 6):
        ns = s + shift
        if ns >= e - 3:
            break
        score = difflib.SequenceMatcher(
            None, _normalize_str(source_text[ns:e]), target, autojunk=False
        ).ratio()
        if score >= best_score:
            best_score, best_s, best_e = score, ns, e

    # Probar mover end → izquierda
    for shift in range(1, 6):
        ne = e - shift
        if ne <= best_s + 3:
            break
        score = difflib.SequenceMatcher(
            None, _normalize_str(source_text[best_s:ne]), target, autojunk=False
        ).ratio()
        if score >= best_score:
            best_score, best_s, best_e = score, best_s, ne

    return best_s, best_e


# =========================
# Core alignment (exact / normalized-exact / fuzzy tokens)
# =========================

def _find_exact(needle: str, hay: str) -> Optional[Tuple[int, int]]:
    if not needle:
        return None
    i = hay.find(needle)
    return (i, i + len(needle)) if i != -1 else None


def _find_normalized_exact(needle: str, hay: str) -> Optional[Tuple[int, int]]:
    """
    Búsqueda exacta sobre strings normalizados y proyección a char offsets en el texto original
    usando un fuzzy “casi exacto” en una vecindad.
    """
    if not needle:
        return None
    nneedle = _normalize_str(needle)
    nhay = _normalize_str(hay)
    i = nhay.find(nneedle)
    if i == -1:
        return None

    # Proyectar grosso modo y refinar con fuzzy local exigente
    approx_char = max(0, int(i * (len(hay) / max(1, len(nhay))) - 10))
    m = _fuzzy_align_tokens(needle, hay, fuzzy_threshold=0.98, start_hint=approx_char, hint_radius=200)
    return m


def _fuzzy_align_tokens(
    extraction_text: str,
    source_text: str,
    fuzzy_threshold: float = 0.75,
    start_hint: Optional[int] = None,
    hint_radius: int = 0,
) -> Optional[Tuple[int, int]]:
    """
    Alineación FUZZY por tokens con ventana de longitud variable.
    - Si start_hint es None: analiza todo el documento.
    - Si hay hint: restringe a un vecindario [start_hint - hint_radius, start_hint + hint_radius] en chars.
    Devuelve (start_char, end_char) o None.
    """
    if not extraction_text or not source_text:
        return None

    # Posible restricción por hint (en chars) → recorta texto de búsqueda
    search_lo, search_hi = 0, len(source_text)
    if start_hint is not None and hint_radius > 0:
        search_lo = max(0, start_hint - hint_radius)
        search_hi = min(len(source_text), start_hint + hint_radius)
        search_text = source_text[search_lo:search_hi]
        offset_base = search_lo
    else:
        search_text = source_text
        offset_base = 0

    # Tokenizar extracción y texto
    ext_tokens = _tokenize(extraction_text)
    src_tokens = _tokenize(search_text)
    if not ext_tokens or not src_tokens:
        return None

    ext_norm = [_normalize_token(t.text) for t in ext_tokens]
    len_e = len(ext_norm)
    # Precompute counts for “overlap” atajo
    ext_counts = Counter(ext_norm)

    # SequenceMatcher como en langextract (b = ext_norm; a = window_norm)
    matcher = difflib.SequenceMatcher(autojunk=False, b=ext_norm)

    best_ratio = 0.0
    best_span_tokens = None  # (start_token_idx, window_size)

    # Mínimo solapamiento de tokens como quick filter
    min_overlap = max(1, int(len_e * fuzzy_threshold))

    # Ventanas de tamaño variable: desde len_e hasta len(src_tokens)
    # (podés cortar arriba si querés acotar max_len_factor)
    for win in range(len_e, len(src_tokens) + 1):
        window = deque(src_tokens[0:win])
        window_norm = [_normalize_token(t.text) for t in window]
        window_counts = Counter(window_norm)

        # Preparamos window_norm en lista mutable
        for start in range(0, len(src_tokens) - win + 1):
            # Atajo por conteo de intersección
            overlap = sum(min(window_counts[x], ext_counts[x]) for x in ext_counts)
            if overlap >= min_overlap:
                matcher.set_seq1(window_norm)
                # matches = suma de tamaños de matching blocks (en tokens)
                matches = sum(size for _, _, size in matcher.get_matching_blocks())
                ratio = matches / len_e if len_e else 0.0
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_span_tokens = (start, win)

            # Slide window (si no es el último)
            if start + win < len(src_tokens):
                old_tok = window.popleft()
                old_norm = _normalize_token(old_tok.text)
                window_counts[old_norm] -= 1
                if window_counts[old_norm] == 0:
                    del window_counts[old_norm]
                new_tok = src_tokens[start + win]
                window.append(new_tok)
                new_norm = _normalize_token(new_tok.text)
                window_counts[new_norm] += 1
                # actualizar lista window_norm en O(win) (suficiente para docs medianos)
                window_norm = [_normalize_token(t.text) for t in window]

    if best_span_tokens and best_ratio >= fuzzy_threshold:
        start_idx, win = best_span_tokens
        t_start = src_tokens[start_idx].start + offset_base
        t_end = src_tokens[start_idx + win - 1].end + offset_base
        # Ajustes de límites y refinado leve
        s, e = _snap_to_token_bounds(source_text, t_start, t_end)
        s, e = _refine_boundaries(extraction_text, source_text, s, e)
        return (s, e)
    return None


# =========================
# Public Aligner class
# =========================

class EntityAligner:
    def __init__(self, fuzzy_threshold: float = 0.75):
        self.fuzzy_threshold = fuzzy_threshold

    def align_one(self, label: Dict[str, Any], text: str, idx: int) -> Extraction:
        attrs = label.get("attrs", {}) or {}
        raw_text = attrs.get("aymurai_alt_text") or label.get("text") or ""
        klass = attrs.get("aymurai_label") or attrs.get("label") or label.get("label") or "ENT"

        # 1) Exacto literal
        m = _find_exact(raw_text, text)
        if m:
            s, e = m
            return Extraction(klass, text[s:e], CharInterval(s, e), AlignmentStatus.MATCH_EXACT, idx, attributes=attrs)

        # 2) Exacto “normalizado”
        m = _find_normalized_exact(raw_text, text)
        if m:
            s, e = m
            return Extraction(klass, text[s:e], CharInterval(s, e), AlignmentStatus.MATCH_FUZZY, idx, attributes=attrs)

        # 3) FUZZY por tokens (ventana/longitud variable)
        m = _fuzzy_align_tokens(raw_text, text, fuzzy_threshold=self.fuzzy_threshold)
        if m:
            s, e = m
            return Extraction(klass, text[s:e], CharInterval(s, e), AlignmentStatus.MATCH_FUZZY, idx, attributes=attrs)

        return Extraction(klass, raw_text, None, AlignmentStatus.NO_MATCH, idx, attributes=attrs)


# =========================
# Convenience API
# =========================

def create_langextract_alignment(document_id: str, text: str, labels: List[Dict[str, Any]], fuzzy_threshold: float = 0.75) -> AnnotatedDocument:
    aligner = EntityAligner(fuzzy_threshold=fuzzy_threshold)
    extractions = [aligner.align_one(lab, text, i + 1) for i, lab in enumerate(labels)]
    return AnnotatedDocument(document_id=document_id, text=text, extractions=extractions)


def validate_alignment(doc: AnnotatedDocument) -> Dict[str, Any]:
    total = len(doc.extractions)
    matched = sum(1 for e in doc.extractions if e.char_interval is not None)
    exact = sum(1 for e in doc.extractions if e.alignment_status == AlignmentStatus.MATCH_EXACT)
    return {
        "total_extractions": total,
        "matched": matched,
        "exact": exact,
        "alignment_accuracy": matched / total if total else 0.0,
        "exact_ratio": exact / total if total else 0.0,
    }


def align_ner_data(example: Dict[str, Any], fuzzy_threshold: float = 0.75) -> tuple[AnnotatedDocument, Dict[str, Any]]:
    """
    example: {
      "id": ...,
      "document": "...",  # o {"text": "..."}
      "labels": [ {"text": "...", "attrs": {...}}, ... ]
    }
    """
    text = example["document"] if isinstance(example["document"], str) else example["document"].get("text", "")
    labels = example.get("labels", [])
    doc = create_langextract_alignment(document_id=str(example.get("id", "doc")), text=text, labels=labels, fuzzy_threshold=fuzzy_threshold)
    return doc, validate_alignment(doc)


# =========================
# Demo opcional
# =========================

if __name__ == "__main__":
    # Pequeña demo manual (no depende de archivos externos):
    example = {
        "id": "demo",
        "document": "En audiencia del día 17 de noviembre de 2023, la Sra. Patricia Gómez compareció junto a Luis Alberto Rivas.",
        "labels": [
            {"text": "17 del mes de noviembre de 2023", "attrs": {"aymurai_label": "FECHA"}},
            {"text": "Patricia   Gomez", "attrs": {"aymurai_label": "PER"}},  # sin tilde/espacios extra
            {"text": "Luis Alberto Rivas", "attrs": {"aymurai_label": "PER"}},
        ],
    }
    doc, stats = align_ner_data(example, fuzzy_threshold=0.75)
    print(stats)
    for e in doc.extractions:
        print(e.extraction_class, e.alignment_status.value, e.char_interval, repr(e.extraction_text))
