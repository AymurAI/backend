# entity_aligner_minimal_flair.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import re, difflib, unicodedata
from flair.tokenization import SpaceTokenizer

# --------------------------
# Tokenizer (Flair)
# --------------------------
_space = SpaceTokenizer()

@dataclass
class Tok:
    text: str
    start: int
    end: int  # exclusive

def _space_tokenize_with_offsets(text: str) -> List[Tok]:
    """
    SpaceTokenizer.run_tokenize(text) -> List[str]
    Convertimos a tokens con offsets buscando cada token desde un cursor.
    """
    raw_tokens = _space.run_tokenize(text)  # List[str]
    out: List[Tok] = []
    i = 0
    n = len(text)
    for t in raw_tokens:
        if not t:
            continue
        # saltar espacios
        while i < n and text[i].isspace():
            i += 1
        # encontrar token a partir de i
        j = text.find(t, i)
        if j == -1:
            # fallback: busco desde 0, última ocurrencia posterior a i
            j = text.find(t)
            if j == -1:
                # si no aparece, lo ignoramos (raro)
                continue
        start = j
        end = j + len(t)
        out.append(Tok(t, start, end))
        i = end
    return out

# --------------------------
# Base dataclasses
# --------------------------
class AlignmentStatus(Enum):
    MATCH_EXACT = "match_exact"
    MATCH_FUZZY = "match_fuzzy"
    NO_MATCH = None

@dataclass
class CharInterval:
    start_pos: int
    end_pos: int

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

# --------------------------
# Helpers
# --------------------------
def _normalize(s: str) -> str:
    s = s.lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s.strip())
    return s

def _normalize_tok(t: str) -> str:
    t = _normalize(t)
    t = re.sub(r"^[\W_]+|[\W_]+$", "", t)   # bordes blandos
    t = re.sub(r"s$", "", t)                # plural simple
    return t

def _snap_to_word_boundaries(text: str, start: int, end: int) -> Tuple[int, int]:
    n = len(text)
    while start > 0 and text[start - 1].isalnum():
        start -= 1
    while end < n and text[end].isalnum():
        end += 1
    return start, end

def _refine_boundaries(entity_text: str, source_text: str, s: int, e: int) -> Tuple[int, int]:
    target = _normalize(entity_text)
    best_s, best_e = s, e
    best = difflib.SequenceMatcher(None, _normalize(source_text[s:e]), target, autojunk=False).ratio()
    # recortar izquierda
    for shift in range(1, 6):
        ns = s + shift
        if ns >= e - 3: break
        r = difflib.SequenceMatcher(None, _normalize(source_text[ns:e]), target, autojunk=False).ratio()
        if r >= best: best, best_s, best_e = r, ns, e
    # recortar derecha
    for shift in range(1, 6):
        ne = e - shift
        if ne <= best_s + 3: break
        r = difflib.SequenceMatcher(None, _normalize(source_text[best_s:ne]), target, autojunk=False).ratio()
        if r >= best: best, best_s, best_e = r, best_s, ne
    return best_s, best_e

# --------------------------
# Core aligner
# --------------------------
class EntityAligner:
    def __init__(self, fuzzy_threshold: float = 0.75):
        self.fuzzy_threshold = fuzzy_threshold

    def _find_exact(self, needle: str, haystack: str) -> Optional[Tuple[int, int]]:
        if not needle:
            return None
        idx = haystack.find(needle)
        return (idx, idx + len(needle)) if idx != -1 else None

    def _find_normalized_exact(self, needle: str, haystack: str) -> Optional[Tuple[int, int]]:
        if not needle:
            return None
        nneedle = _normalize(needle)
        nhay = _normalize(haystack)
        idx = nhay.find(nneedle)
        if idx == -1:
            return None
        approx_char = max(0, int(idx * (len(haystack) / max(1, len(nhay))) - 10))
        return self._fuzzy_align_tokens(needle, haystack, start_hint=approx_char, hint_radius=200, threshold=0.98)

    def _fuzzy_align_tokens(
        self,
        entity_text: str,
        source_text: str,
        start_hint: Optional[int] = None,
        hint_radius: int = 0,
        threshold: float = 0.75,
    ) -> Optional[Tuple[int, int]]:
        """Fuzzy por tokens (Flair SpaceTokenizer) con ventana de tamaño variable."""
        if not entity_text or not source_text:
            return None

        # Restricción opcional por hint en chars
        search_lo, search_hi = 0, len(source_text)
        if start_hint is not None and hint_radius > 0:
            search_lo = max(0, start_hint - hint_radius)
            search_hi = min(len(source_text), start_hint + hint_radius)
            subtext = source_text[search_lo:search_hi]
            base = search_lo
        else:
            subtext = source_text
            base = 0

        ent_toks = _space_tokenize_with_offsets(entity_text)
        src_toks = _space_tokenize_with_offsets(subtext)
        if not ent_toks or not src_toks:
            return None

        ent_norm = [_normalize_tok(t.text) for t in ent_toks if _normalize_tok(t.text)]
        if not ent_norm:
            return None

        # SequenceMatcher setea b = extracción; a = ventana
        matcher = difflib.SequenceMatcher(autojunk=False, b=ent_norm)
        len_e = len(ent_norm)
        best_ratio = 0.0
        best_span = None  # (start_token_idx, window_size)

        # probamos ventanas desde len_e hasta len(src_toks)
        for win in range(len_e, len(src_toks) + 1):
            # ventana inicial
            window_norm = [_normalize_tok(t.text) for t in src_toks[0:win]]
            for i in range(0, len(src_toks) - win + 1):
                if i > 0:
                    # slide 1: actualizar window_norm
                    left = _normalize_tok(src_toks[i - 1].text)
                    right = _normalize_tok(src_toks[i + win - 1].text)
                    # remover left y agregar right (reconstruimos simple para claridad)
                    window_norm = [_normalize_tok(t.text) for t in src_toks[i : i + win]]

                matcher.set_seq1(window_norm)
                matches = sum(size for _, _, size in matcher.get_matching_blocks())
                ratio = matches / len_e
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_span = (i, win)

        if best_span and best_ratio >= threshold:
            i, win = best_span
            s_char = src_toks[i].start + base
            e_char = src_toks[i + win - 1].end + base
            s_char, e_char = _snap_to_word_boundaries(source_text, s_char, e_char)
            s_char, e_char = _refine_boundaries(entity_text, source_text, s_char, e_char)
            return (s_char, e_char)
        return None

    def align_one(self, label: Dict[str, Any], text: str, idx: int) -> Extraction:
        attrs = label.get("attrs", {}) or {}
        raw_text = attrs.get("aymurai_alt_text") or label.get("text") or ""
        klass = attrs.get("aymurai_label") or attrs.get("label") or label.get("label") or "ENT"

        # 1) exacto literal
        m = self._find_exact(raw_text, text)
        if m:
            s, e = m
            return Extraction(klass, text[s:e], CharInterval(s, e), AlignmentStatus.MATCH_EXACT, idx, attributes=attrs)

        # 2) exacto normalizado
        m = self._find_normalized_exact(raw_text, text)
        if m:
            s, e = m
            return Extraction(klass, text[s:e], CharInterval(s, e), AlignmentStatus.MATCH_FUZZY, idx, attributes=attrs)

        # 3) fuzzy por tokens (Flair)
        m = self._fuzzy_align_tokens(raw_text, text, threshold=self.fuzzy_threshold)
        if m:
            s, e = m
            return Extraction(klass, text[s:e], CharInterval(s, e), AlignmentStatus.MATCH_FUZZY, idx, attributes=attrs)

        return Extraction(klass, raw_text, None, AlignmentStatus.NO_MATCH, idx, attributes=attrs)

# --------------------------
# API
# --------------------------
def create_langextract_alignment(document_id: str, text: str, labels: List[Dict[str, Any]], fuzzy_threshold: float = 0.75) -> AnnotatedDocument:
    aligner = EntityAligner(fuzzy_threshold=fuzzy_threshold)
    extractions = [aligner.align_one(lab, text, i + 1) for i, lab in enumerate(labels)]
    return AnnotatedDocument(document_id=document_id, text=text, extractions=extractions)

def validate_alignment(doc: AnnotatedDocument) -> Dict[str, Any]:
    total = len(doc.extractions)
    matched = sum(1 for e in doc.extractions if e.char_interval)
    exact = sum(1 for e in doc.extractions if e.alignment_status == AlignmentStatus.MATCH_EXACT)
    return {
        "total_extractions": total,
        "matched": matched,
        "exact": exact,
        "alignment_accuracy": matched / total if total else 0.0,
        "exact_ratio": exact / total if total else 0.0,
    }

def align_ner_data(example: Dict[str, Any], fuzzy_threshold: float = 0.75) -> Tuple[AnnotatedDocument, Dict[str, Any]]:
    text = example["document"] if isinstance(example["document"], str) else example["document"].get("text", "")
    labels = example.get("labels", [])
    doc = create_langextract_alignment(str(example.get("id", "doc")), text, labels, fuzzy_threshold=fuzzy_threshold)
    return doc, validate_alignment(doc)

# --------------------------
# Demo opcional
# --------------------------
if __name__ == "__main__":
    example = {
        "id": "demo",
        "document": "Rada el 17 de noviembre de 2023 declaró su testimonio ante el tribunal.",
        "labels": [
            {"text": "17 del mes de noviembre de 2023", "attrs": {"aymurai_label": "FECHA"}},
        ],
    }
    doc, stats = align_ner_data(example, fuzzy_threshold=0.75)
    print(stats)
    for e in doc.extractions:
        print(e.extraction_class, e.alignment_status.value, e.char_interval, repr(e.extraction_text))
