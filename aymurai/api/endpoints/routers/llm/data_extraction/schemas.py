from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aymurai.meta.api_interfaces import Document

SearchBackend = Literal["fuzzy", "embeddings", "hybrid"]
SectorMode = Literal["csv", "hierarchy"]


class OrganigramCandidate(BaseModel):
    """One organigram row that could correspond to an extracted destinatario."""

    nombre: str = Field(description="Person's name, as listed in the organigram.")
    cargo: str = Field(description="Cargo/office name, as listed in the organigram.")
    sigla: str = Field(description="Organigram acronym for this cargo.")
    depende_de_cargo: str | None = Field(
        default=None, description="Parent cargo this one reports to, if any."
    )
    ruta_cargos: str = Field(
        description="Full hierarchy path from the top of the organigram down to this cargo."
    )
    score: float = Field(
        description=(
            "Match score for the field this candidate was found for (nombre "
            "or cargo, depending on which list it's in). Scale depends on the "
            "search backend used for the request: 0-100 for 'fuzzy', roughly "
            "0-1 for 'embeddings' and 'hybrid'."
        )
    )


class SectorCandidate(BaseModel):
    """One GCBA sector that a destinatario's nombre/cargo could belong to."""

    sector: str = Field(
        description=(
            "Sector name. When `sector_mode='csv'`, as listed in "
            "destinatario_por_sector.csv; when `sector_mode='hierarchy'`, the "
            "organigram's own top-level entity name (see `search_sector_candidates_from_hierarchy`)."
        )
    )
    score: float = Field(
        description=(
            "Combined score for this sector, weighted by how confident the "
            "organigram search was in `origen_cargo` itself (origen_score, "
            "normalized to [0, 1]) so a cargo that barely made the organigram "
            "ranking doesn't count as much as one that ranked first. With "
            "`sector_mode='csv'` this also factors in the "
            "destinatario_por_sector.csv match score for `origen_cargo`; with "
            "`sector_mode='hierarchy'` there's no such match (the sector is "
            "read directly off the organigram), so this is purely the "
            "organigram-match confidence. Scale depends on the search backend "
            "used for the request: 0-100 for 'fuzzy', roughly 0-1 for "
            "'embeddings' and 'hybrid'."
        )
    )
    origen_campo: Literal["nombre", "cargo", "validado"] = Field(
        description=(
            "Which destinatario field's organigram search (nombre-search or "
            "cargo-search) found the organigram row behind this sector "
            "match -- NOT which field was used to match the sector (that's "
            "always `origen_cargo`, since sector is always inferred from "
            "cargo text). 'validado' means this candidate isn't from the "
            "organigram at all: it's a sector a human already confirmed for "
            "this exact nombre in a past extraction (see "
            "`ValidatedDestinatario`), always listed first."
        )
    )
    origen_nombre: str = Field(
        description=(
            "The organigram row's `nombre` (who currently holds `origen_cargo`, "
            "per the organigram snapshot). When `origen_campo='validado'`, the "
            "nombre as last confirmed by a human instead."
        )
    )
    origen_cargo: str = Field(
        description=(
            "The organigram row's `cargo` -- with `sector_mode='csv'`, this is "
            "the text actually matched against destinatario_por_sector.csv to "
            "produce `score`; with `sector_mode='hierarchy'`, it's just the "
            "organigram candidate's own cargo, kept for reference. Regardless "
            "of `sector_mode`, this is populated the same way whether "
            "`origen_campo` is 'nombre' or 'cargo'. When `origen_campo='validado'`, "
            "the cargo as last confirmed by a human instead (may be empty)."
        )
    )
    origen_score: float = Field(
        description=(
            "The organigram-search score for this row (how well it matched "
            "the destinatario's nombre or cargo, per `origen_campo`). Same "
            "scale as `score`. Always 1.0 when `origen_campo='validado'`, "
            "since it's an exact nombre match, not a fuzzy/embeddings score."
        )
    )


class DestinatarioExtraction(BaseModel):
    """A destinatario as extracted by the LLM, with GCBA sector candidates inferred from the organigram."""

    nombre: str | None = None
    cargo: str | None = None
    destinatario_principal: bool
    sector: str | None = None
    sector_confirmado: str | None = Field(
        default=None,
        description=(
            "The specific GCBA sector a human picked from `candidatos_sector` "
            "(or typed by hand), e.g. 'Ministerio de Hacienda'. Kept separate "
            "from `sector`, which always stays the LLM's macro classification "
            "('GCBA', 'Empresa', ...) -- the frontend shows `sector` and, when "
            "it's 'GCBA', `sector_confirmado`'s options underneath. None until "
            "a human validates this destinatario."
        ),
    )
    candidatos_sector: list[SectorCandidate] = Field(
        default_factory=list,
        description=(
            "Ranked GCBA sector candidates: nombre/cargo are cross-referenced "
            "against the organigram, and the resulting candidate cargos are "
            "then matched against destinatario_por_sector.csv to infer which "
            "sector the destinatario belongs to. Best first. `nombre` and "
            "`cargo` are free-text fields the user can edit directly -- this "
            "list is only meant to help resolve `sector`. Empty when the "
            "LLM's inferred `sector` isn't GCBA, or nombre/cargo are both "
            "missing."
        ),
    )


class DataExtractionResult(BaseModel):
    """Structured recommendation data extracted from a document."""

    numero_recomendacion: str | None = None
    fecha_recomendacion: str | None = None
    destinatarios: list[DestinatarioExtraction] = Field(default_factory=list)
    tema: str | None = None
    subtema: str | None = None
    datos_personales: bool
    contenido_para_publicar: str


class DataExtractionRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document": {
                    "document": [
                        "Ciudad Autónoma de Buenos Aires, 07 de Septiembre de 2022.",
                        "VISTO: ...",
                    ],
                    "document_id": "5d41402a-bc4b-2a76-b971-9d911017c592",
                },
            }
        }
    )

    document: Document = Field(
        ..., description="Extracted document, as returned by /misc/document-extract."
    )
    model: str | None = Field(
        default=None, description="Ollama model override. Defaults to DEFAULT_MODEL."
    )
    search_backend: SearchBackend | None = Field(
        default=None,
        description=(
            "Override for which organigram search backend to use. Defaults to "
            "settings.DATA_EXTRACTION_SEARCH_BACKEND."
        ),
    )
    hybrid_weight: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Only used when search_backend='hybrid': weight given to the "
            "embeddings score (the fuzzy score gets 1 - hybrid_weight). "
            "Defaults to settings.DATA_EXTRACTION_HYBRID_WEIGHT."
        ),
    )
    top_k: int | None = Field(
        default=None,
        description=(
            "Number of organigram candidates (per nombre/cargo field) to use "
            "as evidence when inferring `sector`. Defaults to "
            "settings.DATA_EXTRACTION_TOP_K."
        ),
    )
    sector_mode: SectorMode | None = Field(
        default=None,
        description=(
            "How to resolve `sector` from the organigram candidates. 'csv': "
            "match each candidate's cargo against destinatario_por_sector.csv "
            "(uses sector_top_k/hybrid_weight). 'hierarchy': read the sector "
            "directly off the organigram's own hierarchy (see "
            "`sector_matching.resolve_sector_from_hierarchy` for the exact "
            "rules -- Ministerio, Secretaría/Subsecretaría, AGC, Instituto de "
            "Vivienda de la Ciudad, and Jefatura de Gabinete are each handled "
            "as their own case), ignoring destinatario_por_sector.csv "
            "entirely. Defaults to settings.DATA_EXTRACTION_SECTOR_MODE."
        ),
    )
    sector_top_k: int | None = Field(
        default=None,
        description=(
            "Number of sector-corpus matches to consider per organigram "
            "candidate when inferring `sector`, not just the single best "
            "one. Only used when sector_mode='csv'. Defaults to "
            "settings.DATA_EXTRACTION_SECTOR_TOP_K."
        ),
    )
    nombre_origen_weight: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Discount applied to nombre-origin evidence (vs. cargo-origin, "
            "always full weight) when inferring `sector` -- nombre-search "
            "scores tend to run higher than cargo-search scores on pure text "
            "similarity even though cargo is the more durable signal. "
            "Defaults to settings.DATA_EXTRACTION_NOMBRE_ORIGEN_WEIGHT."
        ),
    )
    max_retries: int | None = Field(
        default=None,
        description="Validation retries against the LLM before failing. Defaults to 2.",
    )
    options: dict[str, Any] | None = Field(
        default=None, description="Ollama chat options override."
    )
