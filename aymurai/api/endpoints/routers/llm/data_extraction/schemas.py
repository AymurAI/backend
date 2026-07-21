from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aymurai.meta.api_interfaces import Document

SearchBackend = Literal["fuzzy", "embeddings", "hybrid"]
SearchFields = Literal["nombre", "cargo", "both"]


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


class DestinatarioExtraction(BaseModel):
    """A destinatario as extracted by the LLM, with independently ranked organigram candidates."""

    nombre: str | None = None
    cargo: str | None = None
    destinatario_principal: bool
    sector: str | None = None
    candidatos_nombre: list[OrganigramCandidate] = Field(
        default_factory=list,
        description=(
            "Ranked organigram candidates for `nombre` (from the nombre-search "
            "alone), best first. Independent from candidatos_cargo -- a person "
            "may no longer hold the cargo the organigram currently lists for "
            "them, so the frontend should let the user pick a nombre and a "
            "cargo separately (e.g. two independent dropdowns), not as a "
            "linked pair. Empty when sector isn't GCBA, nombre is missing, or "
            "search_fields excludes it."
        ),
    )
    candidatos_cargo: list[OrganigramCandidate] = Field(
        default_factory=list,
        description=(
            "Ranked organigram candidates for `cargo` (from the cargo-search "
            "alone), best first. Independent from candidatos_nombre. Empty "
            "when sector isn't GCBA, cargo is missing, or search_fields "
            "excludes it."
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
    search_fields: SearchFields | None = Field(
        default=None,
        description=(
            "Which destinatario field(s) to cross-reference against the "
            "organigram: 'nombre', 'cargo', or 'both'. 'nombre' is fragile "
            "across a change of government; 'cargo' is more durable. Defaults "
            "to settings.DATA_EXTRACTION_SEARCH_FIELDS."
        ),
    )
    top_k: int | None = Field(
        default=None,
        description=(
            "Number of ranked candidates to return per destinatario. Defaults "
            "to settings.DATA_EXTRACTION_TOP_K."
        ),
    )
    max_retries: int | None = Field(
        default=None,
        description="Validation retries against the LLM before failing. Defaults to 2.",
    )
    options: dict[str, Any] | None = Field(
        default=None, description="Ollama chat options override."
    )
