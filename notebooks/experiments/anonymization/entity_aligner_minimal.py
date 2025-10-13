from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import re, difflib, unicodedata

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
    attributes: Optional[Dict[str, Any]] = field(default_factory=dict)

@dataclass
class AnnotatedDocument:
    document_id: str
    text: str
    extractions: List[Extraction]

class EntityAligner:
    def __init__(self, fuzzy_threshold: float = 0.75):
        self.fuzzy_threshold = fuzzy_threshold

    # ----------- helpers de texto -----------
    def _normalize(self, s: str) -> str:
        s = s.lower()
        # remover tildes/diacríticos
        s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
        # quitar puntuación “blanda” pero preservar dígitos/letras y separadores útiles
        s = re.sub(r"[^\w\s/:-]", " ", s)
        # colapsar espacios
        s = re.sub(r"\s+", " ", s.strip())
        return s

    def _snap_to_token_bounds(self, text: str, start: int, end: int) -> Tuple[int, int]:
        n = len(text)
        # expandí para no cortar palabras por la mitad
        while start > 0 and text[start - 1].isalnum():
            start -= 1
        while end < n and text[end].isalnum():
            end += 1
        return start, end

    def _refine_boundaries(self, entity_text: str, source_text: str, s: int, e: int) -> Tuple[int, int]:
        """
        Intenta recortar 1..5 chars a izquierda/derecha si con eso aumenta (o mantiene) la similitud
        contra el target, para eliminar artículos/espacios/comas sobrantes del span.
        """
        target = self._normalize(entity_text)
        best_s, best_e = s, e
        best_score = difflib.SequenceMatcher(
            None, self._normalize(source_text[s:e]), target, autojunk=False
        ).ratio()

        # mover start hacia la derecha
        for shift in range(1, 6):
            ns = s + shift
            if ns >= e - 3:
                break
            score = difflib.SequenceMatcher(
                None, self._normalize(source_text[ns:e]), target, autojunk=False
            ).ratio()
            if score >= best_score:
                best_score, best_s, best_e = score, ns, e

        # mover end hacia la izquierda
        for shift in range(1, 6):
            ne = e - shift
            if ne <= best_s + 3:
                break
            score = difflib.SequenceMatcher(
                None, self._normalize(source_text[best_s:ne]), target, autojunk=False
            ).ratio()
            if score >= best_score:
                best_score, best_s, best_e = score, best_s, ne

        return best_s, best_e

    # ----------- exactos -----------
    def _find_exact(self, needle: str, hay: str) -> Optional[Tuple[int, int]]:
        if not needle:
            return None
        i = hay.find(needle)
        return (i, i + len(needle)) if i != -1 else None

    def _find_normalized_exact(self, needle: str, hay: str) -> Optional[Tuple[int, int]]:
        if not needle:
            return None
        nneedle = self._normalize(needle)
        nhay = self._normalize(hay)
        i = nhay.find(nneedle)
        if i == -1:
            return None
        # proyección burda a índices originales + refinado fuzzy de alta exigencia
        approx_char = max(0, int(i * (len(hay) / max(1, len(nhay))) - 10))
        return self._best_fuzzy_substring(
            entity_text=needle,
            source_text=hay,
            hint_pos=approx_char,
            threshold=0.98,        # casi exacto, pero tolera espacios/acentos
            search_radius=200,
        )

    # ----------- FUZZY variable-length SIN hint -----------
    def _best_fuzzy_substring(
        self,
        entity_text: str,
        source_text: str,
        hint_pos: Optional[int] = None,
        threshold: float = 0.75,
        search_radius: int = 160,
        min_len_factor: float = 0.6,
        max_len_factor: float = 1.6,
        max_len_pad: int = 8,
        step: int = 1,
    ) -> Optional[Tuple[int, int]]:
        """
        Busca el mejor span (start,end) cuya versión normalizada maximiza similarity con entity_text
        en el rango de longitudes permitido. Si hint_pos es None, barre todo el documento.
        """
        if not entity_text:
            return None

        L = max(1, len(entity_text))
        n = len(source_text)

        if hint_pos is None:
            start_lo, start_hi = 0, n
        else:
            start_lo = max(0, hint_pos - search_radius)
            start_hi = min(n, hint_pos + search_radius)

        target = self._normalize(entity_text)
        min_len = max(3, int(L * min_len_factor))
        max_len = min(n, int(L * max_len_factor) + max_len_pad)

        best = None
        best_score = 0.0

        # Heurística: si hay token inicial "fuerte" (primer número o palabra larga), probá seeds ahí
        first_token = re.match(r"\w+", target)
        seed_pat = None
        if first_token:
            t = first_token.group(0)
            if len(t) >= 2:
                # buscar ese token (normalizado) en texto original de manera barata
                # (esto no es exacto-normalizado, solo un filtro para seeds)
                seed_pat = re.compile(re.escape(t), flags=re.IGNORECASE)

        candidate_starts = range(start_lo, start_hi, step)
        if seed_pat:
            seeds = [m.start() for m in seed_pat.finditer(source_text[start_lo:start_hi])]
            if seeds:
                # desplazá seeds al índice global y sumá vecindario
                around = []
                for s in seeds:
                    s_global = start_lo + s
                    around.extend(range(max(start_lo, s_global - 40), min(start_hi, s_global + 1), max(1, step)))
                candidate_starts = sorted(set(around))

        for s in candidate_starts:
            if n - s < min_len:
                break
            e_max = min(n, s + max_len)
            for e in range(s + min_len, e_max, step):
                cand = source_text[s:e]
                score = difflib.SequenceMatcher(
                    None, self._normalize(cand), target, autojunk=False
                ).ratio()
                if score > best_score:
                    best_score, best = score, (s, e)

        if best and best_score >= threshold:
            s, e = best
            s, e = self._snap_to_token_bounds(source_text, s, e)
            s, e = self._refine_boundaries(entity_text, source_text, s, e)
            return (s, e)
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

        # 2) exacto “normalizado” (acentos/espacios)
        m = self._find_normalized_exact(raw_text, text)
        if m:
            s, e = m
            return Extraction(klass, text[s:e], CharInterval(s, e), AlignmentStatus.MATCH_FUZZY, idx, attributes=attrs)

        # 3) fuzzy variable-length sin hint
        m = self._best_fuzzy_substring(raw_text, text, hint_pos=None, threshold=self.fuzzy_threshold)
        if m:
            s, e = m
            return Extraction(klass, text[s:e], CharInterval(s, e), AlignmentStatus.MATCH_FUZZY, idx, attributes=attrs)

        return Extraction(klass, raw_text, None, AlignmentStatus.NO_MATCH, idx, attributes=attrs)

# ----------- API de conveniencia -----------
def create_langextract_alignment(document_id: str, text: str, labels: List[Dict[str, Any]], fuzzy_threshold: float = 0.75) -> AnnotatedDocument:
    aligner = EntityAligner(fuzzy_threshold=fuzzy_threshold)
    extractions = []
    for i, lab in enumerate(labels, start=1):
        extractions.append(aligner.align_one(lab, text, i))
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
    # ejemplo: {"document": "...", "labels": [ { "text": "...", "attrs": {...} }, ... ]}
    text = example["document"] if isinstance(example["document"], str) else example["document"].get("text", "")
    labels = example.get("labels", [])
    doc = create_langextract_alignment(document_id=str(example.get("id", "doc")), text=text, labels=labels, fuzzy_threshold=fuzzy_threshold)
    return doc, validate_alignment(doc)
