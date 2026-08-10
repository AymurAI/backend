from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from aymurai.api.exceptions import AymuraiAPIException
from aymurai.logger import get_logger
from aymurai.settings import settings
from aymurai.transforms.entity_subcategories.bm25 import BM25Scorer

from . import organigram_matching
from .schemas import SearchBackend, SectorCandidate

logger = get_logger(__name__)

SECTOR_CSV_PATH = (
    Path(settings.RESOURCES_BASEPATH)
    / "data"
    / "restricted"
    / "defensoria"
    / "destinatario_por_sector.csv"
)

# Categories present in the CSV that aren't a real GCBA sector, so a
# destinatario should never be resolved to one of these.
EXCLUDED_SECTORS = frozenset(
    {"Obra Social / Prepaga", "Organismos Nacionales", "Empresa"}
)


class SectorDataNotAvailable(AymuraiAPIException):
    status_code = 503
    title = "Sector reference data not available"


@lru_cache(maxsize=1)
def _load_sector_corpus() -> pd.DataFrame:
    """
    Load the destinatario-to-sector reference table, cleaned and filtered.

    Raises:
        SectorDataNotAvailable: If the CSV file is missing.

    Returns:
        pd.DataFrame: One row per (raw destinatario text, sector), excluding
        EXCLUDED_SECTORS, with a `clean_text` column ready for matching.
    """
    if not SECTOR_CSV_PATH.exists():
        raise SectorDataNotAvailable(
            detail=f"Expected sector data at {SECTOR_CSV_PATH}"
        )

    df = pd.read_csv(SECTOR_CSV_PATH).rename(
        columns={"Destinatario": "destinatario", "Destinatario por sector": "sector"}
    )
    df = df.dropna(subset=["destinatario", "sector"])
    df = df[~df["sector"].isin(EXCLUDED_SECTORS)]
    df["clean_text"] = df["destinatario"].map(organigram_matching.clean_cargo)
    return df.reset_index(drop=True)


@lru_cache(maxsize=1)
def _get_sector_embeddings() -> np.ndarray:
    """
    Build (once) and cache L2-normalized embeddings for every sector-corpus row.

    Returns:
        np.ndarray: Shape (n_rows, embedding_dim), one unit-norm vector per row.
    """
    encoder = organigram_matching._get_encoder()
    texts = _load_sector_corpus()["clean_text"].tolist()
    vectors = encoder.batch_encode(
        texts, encoder_type="response_encoder", batch_size=256
    )
    return organigram_matching._l2_normalize(vectors)


@lru_cache(maxsize=1)
def _get_sector_bm25() -> BM25Scorer:
    """
    Build (once) and cache a BM25Scorer over the sector corpus's cleaned text.

    Returns:
        BM25Scorer: Scorer built from the corpus's cleaned text.
    """
    # Texts are already cleaned, so BM25Scorer's normalize_fn is a no-op.
    return BM25Scorer(
        _load_sector_corpus()["clean_text"].tolist(), normalize_fn=lambda t: t
    )


def _sector_fuzzy_scores(query_clean: str) -> np.ndarray:
    """
    Fuzzy score of `query_clean` against every sector-corpus row, unranked.

    Args:
        query_clean (str): Already-cleaned cargo text.

    Returns:
        np.ndarray: 0-100 score per corpus row.
    """
    corpus = _load_sector_corpus()
    return organigram_matching._fuzzy_score_vector(
        query_clean, corpus["clean_text"].tolist()
    )


@lru_cache(maxsize=8192)
def _sector_embeddings_scores(query_clean: str) -> np.ndarray:
    """
    Hybrid sentence-embedding + BM25 score of `query_clean` against every
    sector-corpus row, unranked.

    Cached by query_clean: the expensive part is encoder.encode(), a pure
    function of the query text given the fixed sector corpus/encoder --
    hybrid_weight and nombre_origen_weight (applied elsewhere) don't change
    it, so sweeping either would otherwise re-run the same encode() call for
    the same candidate cargo text over and over.

    Args:
        query_clean (str): Already-cleaned cargo text.

    Returns:
        np.ndarray: Combined score (roughly 0-1) per corpus row.
    """
    encoder = organigram_matching._get_encoder()
    query_vector = encoder.encode([query_clean], encoder_type="question_encoder")[0]
    query_vector = query_vector / max(np.linalg.norm(query_vector), 1e-9)
    sim_scores = _get_sector_embeddings() @ query_vector

    bm25_scores = _get_sector_bm25().score_vector(query_clean)
    return organigram_matching._combine_hybrid_scores(
        sim_scores, bm25_scores, organigram_matching.EMBEDDINGS_BM25_WEIGHT
    )


def _sector_matches(
    cargo_text: str, *, k: int, backend: SearchBackend, hybrid_weight: float
) -> list[tuple[str, float]]:
    """
    Find the top-k sector-corpus rows that best match one candidate cargo text.

    Args:
        cargo_text (str): Raw cargo text (e.g. an organigram candidate's `cargo`).
        k (int): Max number of sector-corpus rows to return.
        backend (SearchBackend): "fuzzy", "embeddings", or "hybrid".
        hybrid_weight (float): Only used when backend="hybrid" -- weight given
            to the embeddings score, in [0, 1]. Ignored otherwise.

    Returns:
        list[tuple[str, float]]: Up to `k` (sector, score) rows, best first.
        Not deduplicated by sector -- several rows can name the same sector.
        Empty if the sector corpus is empty.
    """
    corpus = _load_sector_corpus()
    if corpus.empty:
        return []

    query_clean = organigram_matching.clean_cargo(cargo_text)

    if backend == "fuzzy":
        scores = _sector_fuzzy_scores(query_clean)
    elif backend == "embeddings":
        scores = _sector_embeddings_scores(query_clean)
    else:
        fuzzy_scores = organigram_matching._normalize_scores(
            _sector_fuzzy_scores(query_clean)
        )
        embeddings_scores = organigram_matching._normalize_scores(
            _sector_embeddings_scores(query_clean)
        )
        scores = hybrid_weight * embeddings_scores + (1 - hybrid_weight) * fuzzy_scores

    top_indices = np.argsort(-scores)[:k]
    return [(corpus.iloc[i]["sector"], float(scores[i])) for i in top_indices]


# Scale that a "perfect" organigram-search score sits at for each backend,
# used to normalize origen_score to [0, 1] before it weights the sector score.
_ORIGEN_SCORE_SCALE: dict[SearchBackend, float] = {
    "fuzzy": 100.0,
    "embeddings": 1.0,
    "hybrid": 1.0,
}


def search_sector_candidates(
    candidates: list[tuple[str, str, str, float]],
    *,
    backend: SearchBackend,
    hybrid_weight: float = 0.5,
    sector_top_k: int = 1,
    nombre_origen_weight: float = 1.0,
) -> list[SectorCandidate]:
    """
    Infer the most likely GCBA sector(s) for a destinatario from candidate organigram matches.

    For each candidate (an organigram row matched via nombre-search or
    cargo-search), finds its `cargo`'s `sector_top_k` best-matching sectors
    against destinatario_por_sector.csv (excluding EXCLUDED_SECTORS) -- not
    just the single best one, since a candidate's true sector isn't always
    the argmax match; considering more than one per candidate surfaces
    sectors that a single-best lookup would otherwise never see. Sector is
    always inferred from `cargo` text, regardless of whether `origen_campo`
    is "nombre" or "cargo" (that only says which search found this row).
    Each sector-match score is then weighted by how confident the organigram
    search itself was in this row (`origen_score`, normalized to [0, 1]),
    and additionally discounted by `nombre_origen_weight` when `origen_campo`
    is "nombre" -- full names either match almost exactly or not at all, so
    nombre-search scores tend to run higher than cargo-search scores on pure
    text similarity, even though nombre is the less durable signal (people
    change cargo/government far more often than a cargo's own office
    structure changes). Without this discount, that scoring quirk would let
    nombre-origin evidence dominate cargo-origin evidence in the ranking,
    backwards from what should happen. Sectors are then ranked by the best
    combined score any candidate/match achieved for them.

    Args:
        candidates (list[tuple[str, str, str, float]]): (origen_campo,
            origen_nombre, origen_cargo, origen_score) per organigram
            candidate row -- origen_campo is "nombre" or "cargo" (which
            field-search found this row), origen_nombre/origen_cargo are
            that row's nombre/cargo, origen_score is its organigram-match
            score (same scale as `backend`: 0-100 for 'fuzzy', ~0-1 otherwise).
        backend (SearchBackend): "fuzzy", "embeddings", or "hybrid".
        hybrid_weight (float): Only used when backend="hybrid" -- weight given
            to the embeddings score, in [0, 1]. Ignored otherwise.
        sector_top_k (int): Max number of sector-corpus matches to consider
            per candidate, not just the single best. Higher values surface
            more sector candidates at the cost of including weaker matches.
        nombre_origen_weight (float): Multiplier applied to a candidate's
            combined score when `origen_campo == "nombre"`; cargo-origin
            candidates are never discounted. 1.0 disables the discount.

    Returns:
        list[SectorCandidate]: One entry per distinct sector matched by any
        candidate, sorted by combined score descending. Each keeps a
        reference (origen_campo/origen_nombre/origen_cargo/origen_score) to
        the candidate whose combined score was highest for that sector.
    """
    origen_scale = _ORIGEN_SCORE_SCALE[backend]
    best_by_sector: dict[str, SectorCandidate] = {}

    for origen_campo, origen_nombre, origen_cargo, origen_score in candidates:
        if not origen_cargo:
            continue

        campo_weight = nombre_origen_weight if origen_campo == "nombre" else 1.0
        matches = _sector_matches(
            origen_cargo, k=sector_top_k, backend=backend, hybrid_weight=hybrid_weight
        )
        for sector, sector_score in matches:
            combined_score = sector_score * (origen_score / origen_scale) * campo_weight

            existing = best_by_sector.get(sector)
            if existing is None or combined_score > existing.score:
                best_by_sector[sector] = SectorCandidate(
                    sector=sector,
                    score=combined_score,
                    origen_campo=origen_campo,
                    origen_nombre=origen_nombre,
                    origen_cargo=origen_cargo,
                    origen_score=origen_score,
                )

    return sorted(
        best_by_sector.values(), key=lambda candidate: candidate.score, reverse=True
    )


# --- Hierarchy mode: resolve sector directly from the organigram ------------------


# Administrative umbrella labels present at the top of almost every organigram
# row's ruta_cargos -- not a distinguishing sector on their own, so they're
# skipped when looking for "the first real level" of the hierarchy.
GENERIC_ROOT_LABELS = frozenset(
    {"Jefe de Gobierno", "Jefatura de Gabinete de Ministros"}
)

# Administratively autonomous bodies that always resolve to their own name,
# no matter which ministry/body the organigram happens to nest them under.
# (keyword to search for in a normalized path segment, canonical sector name)
_AUTONOMOUS_BODY_KEYWORDS: list[tuple[str, str]] = [
    ("agencia gubernamental de control", "AGC"),
    ("administracion gubernamental de ingresos publicos", "AGIP"),
    ("instituto de vivienda de la ciudad", "Instituto de Vivienda de la Ciudad"),
    ("copidis", "COPIDIS"),
]

_JEFATURA_GABINETE_KEYWORD = "jefatura de gabinete de ministros"


def _first_non_generic_segment(segments: list[str]) -> str | None:
    """
    First segment of a hierarchy path that isn't a GENERIC_ROOT_LABELS entry.

    Args:
        segments (list[str]): Hierarchy path segments, root first.

    Returns:
        str | None: The first non-generic segment, or None if every segment
        is generic (or the path is empty).
    """
    for segment in segments:
        if segment and segment not in GENERIC_ROOT_LABELS:
            return segment
    return None


def resolve_sector_from_hierarchy(ruta_cargos: str) -> str | None:
    """
    Resolve a sector directly from one organigram row's hierarchy path, per
    a fixed set of business rules (in priority order):

    1. Administratively autonomous bodies (AGC, AGIP, Instituto de Vivienda de
       la Ciudad, COPIDIS -- see `_AUTONOMOUS_BODY_KEYWORDS`), or anything
       nested under one of them, always resolve to that body's own name --
       even though the organigram nests them under a ministry or another
       body (e.g. AGIP under Ministerio de Hacienda y Finanzas, COPIDIS under
       Vicejefatura de Gobierno), they're autonomous and should be their own
       sector, not their parent's.
    2. If a Ministerio appears anywhere in the path -- whether the row's own
       cargo IS the ministerio, or it depends on one at some level -- that
       ministerio is the sector.
    3. Otherwise (no Ministerio anywhere in the path): if a Secretaría
       appears anywhere in the path, that Secretaría is the sector -- even
       when the row's own cargo is a Subsecretaría, since a subsecretaría
       always belongs to its secretaría, not the other way around. A
       Subsecretaría alone, with no Secretaría anywhere above it, is NOT
       enough to satisfy this rule (falls through to 4/5 instead).
    4. Otherwise, if the path still goes through "Jefatura de Gabinete de
       Ministros" (e.g. a body -- Subsecretaría or not -- that hangs
       directly off it with no ministerio/secretaría in between), the
       sector is "Jefatura de Gabinete".
    5. Otherwise, fall back to the first real level of the hierarchy as-is
       (covers standalone top-level bodies like Vicejefatura de Gobierno or
       Procuración General, which don't hang off Jefatura de Gabinete de
       Ministros at all -- including any Subsecretaría nested under them).

    This is purely structural -- doesn't touch destinatario_por_sector.csv.

    Args:
        ruta_cargos (str): Full " > "-joined hierarchy path for one
            organigram row, from `OrganigramCandidate.ruta_cargos`.

    Returns:
        str | None: The resolved sector, or None if the path is empty or
        only made of generic root labels.
    """
    segments = ruta_cargos.split(" > ")
    normalized_segments = [
        organigram_matching.normalize_text(segment) for segment in segments
    ]

    for keyword, canonical_name in _AUTONOMOUS_BODY_KEYWORDS:
        if any(keyword in segment for segment in normalized_segments):
            return canonical_name

    for segment, segment_norm in zip(segments, normalized_segments):
        if segment_norm.startswith("ministerio"):
            return segment

    # "secretaria".startswith excludes "subsecretaria" (it starts with "sub"),
    # so a lone Subsecretaría with no Secretaría above it won't match here.
    for segment, segment_norm in zip(segments, normalized_segments):
        if segment_norm.startswith("secretaria"):
            return segment

    if any(_JEFATURA_GABINETE_KEYWORD in segment for segment in normalized_segments):
        return "Jefatura de Gabinete"

    return _first_non_generic_segment(segments)


def search_sector_candidates_from_hierarchy(
    candidates: list[tuple[str, str, str, float, str]],
    *,
    backend: SearchBackend,
    nombre_origen_weight: float = 1.0,
) -> list[SectorCandidate]:
    """
    Infer sector(s) directly from the organigram's hierarchy, bypassing destinatario_por_sector.csv.

    For each candidate, resolves its sector via `resolve_sector_from_hierarchy`
    instead of matching its cargo against the sector corpus. The combined
    score is just the candidate's own organigram-match confidence
    (normalized to [0, 1], discounted by `nombre_origen_weight` for
    nombre-origin candidates) -- there's no separate sector-match score to
    blend in, since the hierarchy lookup is exact rather than a text match.

    Args:
        candidates (list[tuple[str, str, str, float, str]]): (origen_campo,
            origen_nombre, origen_cargo, origen_score, ruta_cargos) per
            organigram candidate row -- origen_campo is "nombre" or "cargo"
            (which field-search found this row), origen_score is its
            organigram-match score (same scale as `backend`: 0-100 for
            'fuzzy', ~0-1 otherwise), ruta_cargos is its full hierarchy path.
        backend (SearchBackend): Only used to normalize origen_score to [0, 1].
        nombre_origen_weight (float): Multiplier applied to a candidate's
            combined score when `origen_campo == "nombre"`; cargo-origin
            candidates are never discounted. 1.0 disables the discount.

    Returns:
        list[SectorCandidate]: One entry per distinct sector resolved by any
        candidate, sorted by combined score descending. Each keeps a
        reference (origen_campo/origen_nombre/origen_cargo/origen_score) to
        the candidate whose combined score was highest for that sector.
    """
    origen_scale = _ORIGEN_SCORE_SCALE[backend]
    best_by_sector: dict[str, SectorCandidate] = {}

    for (
        origen_campo,
        origen_nombre,
        origen_cargo,
        origen_score,
        ruta_cargos,
    ) in candidates:
        sector = resolve_sector_from_hierarchy(ruta_cargos)
        if sector is None:
            continue

        campo_weight = nombre_origen_weight if origen_campo == "nombre" else 1.0
        combined_score = (origen_score / origen_scale) * campo_weight

        existing = best_by_sector.get(sector)
        if existing is None or combined_score > existing.score:
            best_by_sector[sector] = SectorCandidate(
                sector=sector,
                score=combined_score,
                origen_campo=origen_campo,
                origen_nombre=origen_nombre,
                origen_cargo=origen_cargo,
                origen_score=origen_score,
            )

    return sorted(
        best_by_sector.values(), key=lambda candidate: candidate.score, reverse=True
    )
