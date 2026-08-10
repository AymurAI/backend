from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

from aymurai.api.exceptions import AymuraiAPIException
from aymurai.logger import get_logger
from aymurai.models.sentence_encoder.factory import create_encoder
from aymurai.settings import settings
from aymurai.transforms.entity_subcategories.bm25 import BM25Scorer

from .schemas import OrganigramCandidate, SearchBackend

logger = get_logger(__name__)

ORGANIGRAM_PATH = (
    Path(settings.RESOURCES_BASEPATH)
    / "data"
    / "restricted"
    / "defensoria"
    / "organigram_GCBA.json"
)

EMBEDDING_ENCODER_NAME = "minilm"
EMBEDDINGS_BM25_WEIGHT = 0.5


class OrganigramNotAvailable(AymuraiAPIException):
    status_code = 503
    title = "Organigram data not available"


# --- Text cleaning -----------------------------------------------------------
#
# Role titles after which the following words name the actual cargo, e.g.
# "Secretario de Deportes del Ministerio de ..." -> the role is "Secretario de
# Deportes"; everything from "del Ministerio ..." on is the parent chain. The
# "de" right after the role is optional: some cargos read "Directora General
# Obras en Vías Peatonales" with no "de" before the topic.
CARGO_ROLE_PREFIXES = (
    "ministro",
    "ministra",
    # "General" here is part of the title ("Secretary General"), not the
    # start of the topic clause -- these must come before the bare
    # "secretario"/"secretaria" below, or the alternation matches the
    # shorter prefix first and "general" gets mistaken for the topic (regex
    # `|` alternation picks the first matching branch, not the longest).
    "secretario general",
    "secretaria general",
    "secretario",
    "secretaria",
    "subsecretario",
    "subsecretaria",
    "director general",
    "directora general",
    "director",
    "directora",
    "presidente",
    "presidenta",
    "titular",
    "jefe",
    "jefa",
    "interventor",
    "interventora",
    "coordinador",
    "coordinadora",
)
CARGO_ROLE_PATTERN = re.compile(
    r"^(" + "|".join(CARGO_ROLE_PREFIXES) + r")\b(?:\s+(?:de\s+)?)?"
)

# del/de la/de only counts as the parent-chain boundary when followed by an
# actual parent-institution noun -- otherwise "del"/"de la" inside a compound
# office name (e.g. "Registro del Estado Civil") gets mistaken for it.
PARENT_INSTITUTION_KEYWORDS = (
    "ministerio",
    "secretaria",
    "subsecretaria",
    "gobierno",
    "jefatura",
    "agencia",
    "ente",
    "sindicatura",
    "procuracion",
)
CARGO_PARENT_MARKERS = re.compile(
    r"\s*,?\s+(?:dependiente\s+)?(?:del|de la|de)\s+"
    r"(?=(?:" + "|".join(PARENT_INSTITUTION_KEYWORDS) + r")\b)"
)

# Boilerplate that shows up in almost every extracted `cargo` but never in the
# organigram's own `cargo` values, so it only adds noise to the match.
CARGO_NOISE_PATTERNS = [
    r"\bgobierno de la ciudad autonoma de buenos aires\b",
    r"\bgobierno de la ciudad de buenos aires\b",
    r"\bciudad autonoma de buenos aires\b",
    r"\bciudad de buenos aires\b",
]


def normalize_text(value: str | None) -> str:
    """
    Lowercase + strip accents, so matching ignores casing/tildes.

    Args:
        value (str | None): Text to normalize.

    Returns:
        str: Normalized text, or "" if value is None.
    """
    if value is None:
        return ""
    value = str(value).strip().lower()
    value = unicodedata.normalize("NFKD", value)
    return "".join(char for char in value if not unicodedata.combining(char))


def _extract_cargo_role(text: str) -> str:
    """
    Keep only the "<role> de <topic>" clause, dropping the "del/dependiente
    de/de la ..." parent-institution chain that follows a role title.

    Args:
        text (str): Already-normalized cargo text.

    Returns:
        str: Text with the parent-institution chain removed, if a role prefix was found.
    """
    match = CARGO_ROLE_PATTERN.match(text)
    if not match:
        return text
    rest = text[match.end() :]
    parent_match = CARGO_PARENT_MARKERS.search(rest)
    topic = (rest[: parent_match.start()] if parent_match else rest).strip()
    if not topic:
        # Bare role title with nothing after it (e.g. "Secretaría General"
        # on its own) -- no topic to prepend "de" to.
        return match.group(1).strip()
    first_word = topic.split(" ", 1)[0]
    if first_word not in ("de", "del", "dependiente"):
        topic = f"de {topic}"
    return f"{match.group(1)} {topic}".strip()


def _strip_noise_and_trailing(text: str) -> str:
    """
    Remove GCBA boilerplate phrases and any dangling trailing preposition.

    Args:
        text (str): Already-normalized cargo text.

    Returns:
        str: Cleaned text.
    """
    for pattern in CARGO_NOISE_PATTERNS:
        text = re.sub(pattern, " ", text)
    text = re.sub(
        r"\b(del|de la|de|dependiente(?: del| de la| de)?)\s*$", "", text.strip()
    )
    return re.sub(r"\s+", " ", text).strip()


def clean_cargo(value: str | None) -> str:
    """
    Normalize, extract the role-prefix clause, and strip GCBA boilerplate.

    Args:
        value (str | None): Raw cargo text.

    Returns:
        str: Cleaned cargo text, ready for matching.
    """
    return _strip_noise_and_trailing(_extract_cargo_role(normalize_text(value)))


# --- Organigram loading --------------------------------------------------------


def _iter_people_with_dependency(node, parent=None, path=None):
    """
    Recursively walk the organigram JSON tree, yielding one dict per person.

    Args:
        node (dict | list): Current organigram node (or list of nodes) being walked.
        parent (dict | None): The immediate parent node's {"cargo", "sigla"}, if any.
        path (list[str] | None): Cargo names from the root down to `node`, for `ruta_cargos`.

    Yields:
        dict: {"nombre", "cargo", "sigla", "depende_de_cargo", "depende_de_sigla",
        "ruta_cargos"} for every person found under `node`.
    """
    if path is None:
        path = []

    if isinstance(node, list):
        for child in node:
            yield from _iter_people_with_dependency(child, parent=parent, path=path)
        return

    if not isinstance(node, dict):
        return

    cargo = str(node.get("cargo", "")).strip()
    sigla = str(node.get("sigla", "")).strip()
    nombre = str(node.get("nombre", "")).strip()
    current_path = [*path, cargo] if cargo else path

    if nombre:
        yield {
            "nombre": nombre,
            "cargo": cargo,
            "sigla": sigla,
            "depende_de_cargo": (parent or {}).get("cargo"),
            "depende_de_sigla": (parent or {}).get("sigla"),
            "ruta_cargos": " > ".join(current_path),
        }

    current = {"cargo": cargo, "sigla": sigla}
    for child in node.get("dependencias", []):
        yield from _iter_people_with_dependency(
            child, parent=current, path=current_path
        )


@lru_cache(maxsize=1)
def _load_organigram_people() -> pd.DataFrame:
    """
    Load and flatten the GCBA organigram into one row per person.

    Raises:
        OrganigramNotAvailable: If the organigram JSON file is missing.

    Returns:
        pd.DataFrame: One row per person, with nombre/cargo/sigla/hierarchy columns.
    """
    if not ORGANIGRAM_PATH.exists():
        raise OrganigramNotAvailable(
            detail=f"Expected organigram data at {ORGANIGRAM_PATH}"
        )

    with ORGANIGRAM_PATH.open(encoding="utf-8") as f:
        organigram = json.load(f)

    return pd.DataFrame(_iter_people_with_dependency(organigram))


# --- Shared cleaning helper --------------------------------------------------


def _cleaned_query_and_choices(query: str, field: str) -> tuple[str, list[str]]:
    """
    Clean a query and the organigram's own field values the same way.

    Args:
        query (str): Raw destinatario field text (nombre or cargo).
        field (str): "nombre" or "cargo".

    Returns:
        tuple[str, list[str]]: (cleaned query, cleaned organigram values).
    """
    clean = clean_cargo if field == "cargo" else normalize_text
    return clean(query), _cleaned_field_texts(field)


# --- Fuzzy backend --------------------------------------------------------------


def _fuzzy_score_vector(query_clean: str, choices: list[str]) -> np.ndarray:
    """
    Score `query_clean` against every choice with rapidfuzz, unranked.

    Args:
        query_clean (str): Already-cleaned query text.
        choices (list[str]): Already-cleaned organigram values, one per row.

    Returns:
        np.ndarray: 0-100 score per row, in the same order as `choices`.
    """
    return np.asarray(
        process.cdist([query_clean], choices, scorer=fuzz.token_set_ratio)[0],
        dtype=np.float64,
    )


def _search_fuzzy(query: str, *, field: str, limit: int) -> pd.DataFrame:
    """
    Fuzzy-match `query` against organigram_people[field], ranked by similarity.

    Args:
        query (str): Raw destinatario field text (nombre or cargo).
        field (str): "nombre" or "cargo".
        limit (int): Max rows to return.

    Returns:
        pd.DataFrame: Top matches with a 0-100 `score` column, best first.
    """
    organigram_people = _load_organigram_people()
    query_clean, choices = _cleaned_query_and_choices(query, field)
    scores = _fuzzy_score_vector(query_clean, choices)

    top_indices = np.argsort(-scores)[:limit]
    result = organigram_people.iloc[top_indices].copy()
    result["score"] = scores[top_indices]
    return result.reset_index(drop=True)


# --- Embeddings backend ----------------------------------------------------------


@lru_cache(maxsize=1)
def _get_encoder():
    """
    Build (once) the sentence-transformers encoder used by the embeddings backend.

    Returns:
        BaseSentenceEncoder: The configured `minilm` encoder instance.
    """
    return create_encoder(encoder_type=EMBEDDING_ENCODER_NAME)


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    """
    L2-normalize each row of a matrix so dot products become cosine similarity.

    Args:
        vectors (np.ndarray): Array of shape (n, dim) to normalize row-wise.

    Returns:
        np.ndarray: Same shape as `vectors`, each row unit-norm.
    """
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.clip(norms, 1e-9, None)


def _cleaned_field_texts(field: str) -> list[str]:
    """
    Clean every organigram_people[field] value, in row order.

    Args:
        field (str): "nombre" or "cargo".

    Returns:
        list[str]: Cleaned text for each organigram row, same order as the DataFrame.
    """
    organigram_people = _load_organigram_people()
    clean = clean_cargo if field == "cargo" else normalize_text
    return organigram_people[field].map(clean).tolist()


@lru_cache(maxsize=None)
def _get_field_embeddings(field: str) -> np.ndarray:
    """
    Build (once per field) and cache the L2-normalized embeddings for every organigram row.

    Args:
        field (str): "nombre" or "cargo".

    Returns:
        np.ndarray: Shape (n_rows, embedding_dim), one unit-norm vector per row.
    """
    encoder = _get_encoder()
    texts = _cleaned_field_texts(field)
    vectors = encoder.batch_encode(
        texts, encoder_type="response_encoder", batch_size=256
    )
    return _l2_normalize(vectors)


@lru_cache(maxsize=None)
def _get_field_bm25(field: str) -> BM25Scorer:
    """
    Build (once per field) and cache a BM25Scorer over the organigram's values.

    Args:
        field (str): "nombre" or "cargo".

    Returns:
        BM25Scorer: Scorer built from the field's cleaned text (see
        `aymurai.transforms.entity_subcategories.bm25.BM25Scorer`).
    """
    # Texts are already cleaned, so BM25Scorer's normalize_fn is a no-op.
    return BM25Scorer(_cleaned_field_texts(field), normalize_fn=lambda t: t)


def _combine_hybrid_scores(
    sim_scores: np.ndarray, bm25_scores: np.ndarray, bm25_weight: float
) -> np.ndarray:
    """
    Blend cosine-similarity and BM25 scores into one score vector.

    Args:
        sim_scores (np.ndarray): Cosine similarity per row.
        bm25_scores (np.ndarray): BM25 score per row, same order as `sim_scores`.
        bm25_weight (float): Weight given to `bm25_scores` after max-normalizing
            both vectors to [0, 1]; `sim_scores` gets `1 - bm25_weight`. If
            <= 0, `sim_scores` is returned unchanged (no BM25 blend at all).

    Returns:
        np.ndarray: Combined score per row.
    """
    if bm25_weight <= 0:
        return sim_scores

    bm25_max = bm25_scores.max() if bm25_scores.size else 0.0
    sim_max = sim_scores.max() if sim_scores.size else 0.0
    bm25_norm = (
        bm25_scores / (bm25_max + 1e-9) if bm25_max > 0 else np.zeros_like(bm25_scores)
    )
    sim_norm = (
        sim_scores / (sim_max + 1e-9) if sim_max > 0 else np.zeros_like(sim_scores)
    )

    return bm25_weight * bm25_norm + (1 - bm25_weight) * sim_norm


@lru_cache(maxsize=8192)
def _embeddings_score_vector(query_clean: str, field: str) -> np.ndarray:
    """
    Score `query_clean` against every organigram_people[field] value with the
    sentence-embedding + BM25 hybrid, unranked.

    Cached by (query_clean, field): the expensive part is encoder.encode(),
    a pure function of the query text given the fixed corpus/encoder --
    hybrid_weight (applied later, outside this function) doesn't change it,
    so repeated calls across a hybrid_weight/nombre_origen_weight sweep would
    otherwise re-run the same encode() for the same text every time.

    Args:
        query_clean (str): Already-cleaned query text.
        field (str): "nombre" or "cargo".

    Returns:
        np.ndarray: Combined score (roughly 0-1) per row.
    """
    encoder = _get_encoder()
    field_embeddings = _get_field_embeddings(field)
    query_vector = encoder.encode([query_clean], encoder_type="question_encoder")[0]
    query_vector = query_vector / max(np.linalg.norm(query_vector), 1e-9)
    sim_scores = field_embeddings @ query_vector

    bm25_scores = _get_field_bm25(field).score_vector(query_clean)
    return _combine_hybrid_scores(sim_scores, bm25_scores, EMBEDDINGS_BM25_WEIGHT)


def _search_embeddings(query: str, *, field: str, limit: int) -> pd.DataFrame:
    """
    Hybrid sentence-embedding + BM25 search over organigram_people[field].

    Mirrors aymurai.transforms.entity_subcategories.sentence_transformer's
    SentenceTransformerSubcategorizer (cosine similarity against cached
    embeddings, blended with BM25), applied to organigram rows instead of
    taxonomy subcategories. Cleaned with the same `clean_cargo`/`normalize_text`
    as the fuzzy backend -- keeping the parent-institution chain in the
    compared text made this scorer drift toward the parent institution
    instead of the specific office (confirmed on real corpus data).

    Args:
        query (str): Raw destinatario field text (nombre or cargo).
        field (str): "nombre" or "cargo".
        limit (int): Max rows to return.

    Returns:
        pd.DataFrame: Top matches with a `score` column (roughly 0-1), best first.
    """
    organigram_people = _load_organigram_people()
    query_clean, _ = _cleaned_query_and_choices(query, field)
    scores = _embeddings_score_vector(query_clean, field)

    top_indices = np.argsort(-scores)[:limit]
    result = organigram_people.iloc[top_indices].copy()
    result["score"] = scores[top_indices]
    return result.reset_index(drop=True)


def _normalize_scores(scores: np.ndarray) -> np.ndarray:
    """
    Max-normalize a score vector to roughly [0, 1].

    Args:
        scores (np.ndarray): Raw score per row, any positive scale.

    Returns:
        np.ndarray: `scores` divided by its own max (all zeros if `scores` is
        empty or all-zero, instead of dividing by zero).
    """
    max_score = scores.max() if scores.size else 0.0
    return scores / (max_score + 1e-9) if max_score > 0 else np.zeros_like(scores)


def _search_hybrid(
    query: str, *, field: str, limit: int, hybrid_weight: float
) -> pd.DataFrame:
    """
    Weighted combination of the fuzzy and embeddings backends.

    Computes both scorers over the *entire* organigram (not just each one's
    own top-N) so the two score vectors can be normalized and combined before
    ranking, instead of merging two already-truncated top-N lists.

    Args:
        query (str): Raw destinatario field text (nombre or cargo).
        field (str): "nombre" or "cargo".
        limit (int): Max rows to return.
        hybrid_weight (float): Weight given to the embeddings score, in
            [0, 1]; the fuzzy score gets `1 - hybrid_weight`. 0.5 is equal parts.

    Returns:
        pd.DataFrame: Top matches with a `score` column (roughly 0-1), best first.
    """
    organigram_people = _load_organigram_people()
    query_clean, choices = _cleaned_query_and_choices(query, field)

    fuzzy_scores = _normalize_scores(_fuzzy_score_vector(query_clean, choices))
    embeddings_scores = _normalize_scores(_embeddings_score_vector(query_clean, field))

    combined = hybrid_weight * embeddings_scores + (1 - hybrid_weight) * fuzzy_scores

    top_indices = np.argsort(-combined)[:limit]
    result = organigram_people.iloc[top_indices].copy()
    result["score"] = combined[top_indices]
    return result.reset_index(drop=True)


_SEARCH_FUNCTIONS = {
    "fuzzy": _search_fuzzy,
    "embeddings": _search_embeddings,
}


# --- Public API ------------------------------------------------------------------


def search_candidates(
    *,
    nombre: str | None,
    cargo: str | None,
    sector: str | None,
    backend: SearchBackend,
    top_k: int,
    hybrid_weight: float = 0.5,
) -> dict[str, list[OrganigramCandidate]]:
    """
    Cross-reference a destinatario's nombre/cargo against the organigram.

    Runs a nombre-search and a cargo-search with the selected backend and
    returns each as its own independently ranked list -- NOT merged into one.
    A nombre candidate is not necessarily tied to the cargo candidate from the
    same organigram row: the person named X may no longer hold the cargo Y
    the organigram lists for them (or vice versa), so the frontend should let
    the user pick a nombre and a cargo separately (e.g. two independent
    dropdowns), not as a linked pair.

    Args:
        nombre (str | None): Extracted destinatario name.
        cargo (str | None): Extracted destinatario cargo/role.
        sector (str | None): Extracted destinatario sector.
        backend (SearchBackend): "fuzzy", "embeddings", or "hybrid".
        top_k (int): Max number of candidates to return per field.
        hybrid_weight (float): Only used when backend="hybrid" -- weight given
            to the embeddings score, in [0, 1]. Ignored otherwise.

    Returns:
        dict[str, list[OrganigramCandidate]]: {"nombre": [...], "cargo": [...]},
        each ranked best first. A field's list is empty when sector isn't
        GCBA or that field's value is missing.
    """
    empty: dict[str, list[OrganigramCandidate]] = {"nombre": [], "cargo": []}
    if normalize_text(sector) != "gcba":
        return empty

    field_values = {"nombre": nombre, "cargo": cargo}

    if backend == "hybrid":

        def search_fn(query: str, *, field: str, limit: int) -> pd.DataFrame:
            """Adapts _search_hybrid to the (query, field, limit) shape the other backends use.

            Args:
                query (str): Raw destinatario field text (nombre or cargo).
                field (str): "nombre" or "cargo".
                limit (int): Max rows to return.

            Returns:
                pd.DataFrame: See `_search_hybrid`.
            """
            return _search_hybrid(
                query, field=field, limit=limit, hybrid_weight=hybrid_weight
            )

    else:
        search_fn = _SEARCH_FUNCTIONS[backend]

    result: dict[str, list[OrganigramCandidate]] = {"nombre": [], "cargo": []}
    for field in ("nombre", "cargo"):
        value = field_values[field]
        if not value:
            continue

        df = search_fn(value, field=field, limit=top_k)
        result[field] = [
            OrganigramCandidate(
                nombre=row["nombre"],
                cargo=row["cargo"],
                sigla=row["sigla"],
                depende_de_cargo=row.get("depende_de_cargo"),
                ruta_cargos=row["ruta_cargos"],
                score=float(row["score"]),
            )
            for _, row in df.iterrows()
        ]

    return result
