from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel, model_validator
from sqlmodel import Session

from aymurai.api.exceptions import AymuraiAPIException
from aymurai.database.crud.data_extraction.data_extraction import (
    data_extraction_create_or_update,
    data_extraction_get,
)
from aymurai.database.crud.data_extraction.validated_destinatario import (
    validated_destinatario_get_by_cargo,
    validated_destinatario_get_by_nombre,
)
from aymurai.llm_providers import OllamaLLMProvider
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import Document
from aymurai.settings import settings
from aymurai.utils.yaml_data import load_yaml

from . import organigram_matching, sector_matching
from .schemas import (
    DataExtractionResult,
    DestinatarioExtraction,
    SearchBackend,
    SectorCandidate,
    SectorMode,
)

logger = get_logger(__name__)

DEFAULT_MODEL = settings.MODEL
DEFAULT_OPTIONS = {"num_ctx": 32_768, "num_predict": 8192}
DEFAULT_MAX_RETRIES = 2
PROMPT_CONFIG_PATH = (
    Path(settings.RESOURCES_BASEPATH) / "llm" / "defensoria_extractor.yml"
)


class LLMValidationError(AymuraiAPIException):
    status_code = 502
    title = "LLM output failed validation"


def _build_fields_block(fields: dict[str, str]) -> str:
    """
    Convert the fields dict from the YAML config into a Markdown block for the prompt.

    Args:
        fields (dict[str, str]): Field name -> description.

    Returns:
        str: Markdown-formatted list of fields.
    """
    lines = []
    for field, description in fields.items():
        desc = str(description).strip().replace("\n", " ")
        lines.append(f"- **{field}**: {desc}")
    return "\n".join(lines)


def _build_system_prompt(config: dict[str, Any]) -> str:
    """
    Build the full system prompt from the loaded YAML config.

    Args:
        config (dict[str, Any]): Parsed defensoria_extractor.yml content.

    Returns:
        str: Formatted system prompt, including the taxonomy and output schema.
    """
    prompts = config["system-prompts"]
    fields = config["fields"]
    taxonomy = config["taxonomy"]
    schema = config["output-format"]["schema"]

    schema_json = json.dumps(schema, ensure_ascii=False, indent=2)

    return f"""{prompts["information-extraction"]}

{prompts["extraction-guidelines"]}
# Campos a extraer

{_build_fields_block(fields)}

# Taxonomía de temas y subtemas

{taxonomy}

# Formato de salida (JSON)

Responde exclusivamente con un objeto JSON válido con la siguiente estructura:

```json
{schema_json}
```
"""


def _load_config() -> dict[str, Any]:
    """
    Load the defensoria_extractor.yml prompt config.

    Raises:
        RuntimeError: If the file is missing or malformed.

    Returns:
        dict[str, Any]: Parsed YAML content.
    """
    try:
        return load_yaml(str(PROMPT_CONFIG_PATH))
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"data-extraction prompt config not found at {PROMPT_CONFIG_PATH}"
        ) from exc


_CONFIG = _load_config()
# Subtemas are kept as an ordered tuple (not a set) so subtemas_disponibles
# can preserve the taxonomy's own order.
_TAXONOMY: dict[str, tuple[str, ...]] = {
    tema: tuple(subtemas)
    for entry in yaml.safe_load(_CONFIG["taxonomy"])
    for tema, subtemas in entry.items()
}
Tema = Literal[tuple(_TAXONOMY)]
SYSTEM_PROMPT = _build_system_prompt(_CONFIG)


class _LLMDestinatario(BaseModel):
    """Raw destinatario shape as validated straight out of the LLM response."""

    nombre: str | None = None
    cargo: str | None = None
    destinatario_principal: bool
    sector: str | None = None


class _LLMExtraction(BaseModel):
    """Raw extraction shape as validated straight out of the LLM response."""

    numero_recomendacion: str | None = None
    fecha_recomendacion: str | None = None
    destinatarios: list[_LLMDestinatario]
    tema: Tema | None = None
    subtema: str | None = None
    datos_personales: bool
    contenido_para_publicar: str

    taxonomy: ClassVar[dict[str, tuple[str, ...]]] = _TAXONOMY

    @model_validator(mode="after")
    def _validate_tema_subtema(self) -> "_LLMExtraction":
        """Ensures `subtema` (if set) belongs to the taxonomy's list for `tema`.

        Raises:
            ValueError: If `subtema` is set without a `tema`, or doesn't
                belong to that `tema`'s valid subtemas.

        Returns:
            _LLMExtraction: `self`, unchanged, once validation passes.
        """
        if self.subtema is None:
            return self

        if self.tema is None:
            raise ValueError("No se puede especificar un subtema sin un tema")

        valid_subtemas = self.taxonomy[self.tema]
        if self.subtema not in valid_subtemas:
            raise ValueError(
                f"El subtema {self.subtema!r} no pertenece al tema "
                f"{self.tema!r}. Subtemas válidos: {sorted(valid_subtemas)}"
            )

        return self


def _parse_json_object(raw_output: str) -> dict[str, Any]:
    """
    Extract the first valid JSON object from a model response.

    Args:
        raw_output (str): Raw text returned by the LLM.

    Raises:
        ValueError: If no valid JSON object is found.

    Returns:
        dict[str, Any]: The parsed JSON object.
    """
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_output.strip())
    decoder = json.JSONDecoder()

    for start, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("No valid JSON object found in model response")


def _build_validation_retry_prompt(validation_error: str, previous_output: str) -> str:
    """
    Build a follow-up system prompt asking the model to fix a validation error.

    Args:
        validation_error (str): Error message from the failed validation attempt.
        previous_output (str): The model's previous (invalid) response.

    Returns:
        str: System prompt including the correction instructions.
    """
    return f"""{SYSTEM_PROMPT}

# Corrección obligatoria

Tu respuesta anterior no pasó la validación automática.
Devuelve exclusivamente un objeto JSON válido, sin Markdown ni texto adicional.

Error de validación:
{validation_error}

Respuesta anterior:
{previous_output}
"""


async def _extract_with_retry(
    document_text: str,
    *,
    model: str,
    options: dict[str, Any],
    max_retries: int,
) -> _LLMExtraction:
    """
    Call the LLM and validate its output, retrying with the validation error
    fed back to the model on failure.

    Args:
        document_text (str): Full document text to extract data from.
        model (str): Ollama model name.
        options (dict[str, Any]): Ollama chat options.
        max_retries (int): Number of retries after the first attempt.

    Raises:
        LLMValidationError: If validation never succeeds within max_retries.

    Returns:
        _LLMExtraction: The validated extraction.
    """
    system_prompt = SYSTEM_PROMPT
    last_error: str | None = None
    last_output: str = ""

    for attempt in range(max_retries + 1):
        provider = OllamaLLMProvider(model=model, system_prompt=system_prompt)
        response = await provider.async_generate(prompt=document_text, options=options)
        last_output = response.text

        try:
            parsed = _parse_json_object(last_output)
            return _LLMExtraction.model_validate(parsed)
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                f"data-extraction validation failed (attempt {attempt + 1}): {exc}"
            )
            system_prompt = _build_validation_retry_prompt(last_error, last_output)

    raise LLMValidationError(
        detail=f"Validation failed after {max_retries + 1} attempts: {last_error}"
    )


def _validated_candidate(
    raw: _LLMDestinatario,
    session: Session,
) -> SectorCandidate | None:
    """
    Look up a previously human-validated sector for this destinatario.

    Tries an exact nombre match first; if there's none (or no nombre at
    all), falls back to an exact match on the LLM's cargo -- e.g. the same
    office was validated before under a different (or missing) nombre.

    Args:
        raw (_LLMDestinatario): Destinatario as extracted by the LLM.
        session (Session): SQLAlchemy session.

    Returns:
        SectorCandidate | None: A candidate built from the validated record,
        meant to be listed first (ahead of organigram-derived candidates), or
        None if this destinatario isn't GCBA, or neither nombre nor cargo
        ever matched a validated record.
    """
    if organigram_matching.normalize_text(raw.sector) != "gcba":
        return None

    validated = None
    if raw.nombre:
        validated = validated_destinatario_get_by_nombre(
            organigram_matching.normalize_text(raw.nombre), session
        )
    if not validated and raw.cargo:
        validated = validated_destinatario_get_by_cargo(
            organigram_matching.normalize_text(raw.cargo), session
        )
    if not validated:
        return None

    return SectorCandidate(
        sector=validated.sector,
        score=1.0,
        origen_campo="validado",
        origen_nombre=validated.nombre,
        origen_cargo=validated.cargo or "",
        origen_score=1.0,
    )


def _build_destinatario(
    raw: _LLMDestinatario,
    *,
    backend: SearchBackend,
    top_k: int,
    hybrid_weight: float,
    sector_mode: SectorMode,
    sector_top_k: int,
    nombre_origen_weight: float,
    session: Session,
) -> DestinatarioExtraction:
    """
    Cross-reference one destinatario against the organigram to infer its GCBA sector.

    `nombre`/`cargo` are passed through unchanged (free-text fields the user
    can edit directly). The organigram candidates found for them are only
    used internally, as evidence to resolve `candidatos_sector`. If this
    exact nombre was already validated by a human in a past extraction, that
    sector is listed first, ahead of the organigram-derived candidates.

    Args:
        raw (_LLMDestinatario): Destinatario as extracted by the LLM.
        backend (SearchBackend): Organigram/sector search backend to use.
        top_k (int): Max number of organigram candidates (per field) to use
            as sector evidence.
        hybrid_weight (float): Weight given to the embeddings score when
            backend="hybrid"; ignored otherwise.
        sector_mode (SectorMode): "csv" matches organigram candidates against
            destinatario_por_sector.csv; "hierarchy" reads the sector
            directly off the organigram's own hierarchy instead.
        sector_top_k (int): Max number of sector-corpus matches to consider
            per organigram candidate, not just the single best one. Only
            used when sector_mode="csv".
        nombre_origen_weight (float): Discount applied to nombre-origin
            evidence (vs. cargo-origin, always full weight) when inferring
            `sector`.
        session (Session): SQLAlchemy session, used to look up a previously
            validated sector for this nombre.

    Returns:
        DestinatarioExtraction: Public destinatario with ranked sector candidates.
    """
    validated_candidate = _validated_candidate(raw, session)

    organigram_matches = organigram_matching.search_candidates(
        nombre=raw.nombre,
        cargo=raw.cargo,
        sector=raw.sector,
        backend=backend,
        top_k=top_k,
        hybrid_weight=hybrid_weight,
    )

    if sector_mode == "hierarchy":
        hierarchy_candidates = [
            (
                field,
                candidate.nombre,
                candidate.cargo,
                candidate.score,
                candidate.ruta_cargos,
            )
            for field, field_candidates in organigram_matches.items()
            for candidate in field_candidates
        ]
        candidatos_sector = sector_matching.search_sector_candidates_from_hierarchy(
            hierarchy_candidates,
            backend=backend,
            nombre_origen_weight=nombre_origen_weight,
        )
    else:
        candidates = [
            (field, candidate.nombre, candidate.cargo, candidate.score)
            for field, field_candidates in organigram_matches.items()
            for candidate in field_candidates
        ]
        candidatos_sector = sector_matching.search_sector_candidates(
            candidates,
            backend=backend,
            hybrid_weight=hybrid_weight,
            sector_top_k=sector_top_k,
            nombre_origen_weight=nombre_origen_weight,
        )

    if validated_candidate:
        candidatos_sector = [validated_candidate, *candidatos_sector]

    return DestinatarioExtraction(
        nombre=raw.nombre,
        cargo=raw.cargo,
        destinatario_principal=raw.destinatario_principal,
        sector=raw.sector,
        candidatos_sector=candidatos_sector,
    )


async def run_data_extraction(
    document: Document,
    session: Session,
    *,
    model: str | None = None,
    search_backend: SearchBackend | None = None,
    hybrid_weight: float | None = None,
    top_k: int | None = None,
    sector_mode: SectorMode | None = None,
    sector_top_k: int | None = None,
    nombre_origen_weight: float | None = None,
    max_retries: int | None = None,
    options: dict[str, Any] | None = None,
    use_cache: bool = True,
) -> DataExtractionResult:
    """
    Run the full data-extraction pipeline: LLM extraction + organigram cross-reference.

    If `use_cache` and `document.document_id` was already extracted before,
    returns the persisted result directly instead of calling the LLM again --
    the human-validated result if one was saved (see
    `data_extraction_set_validation`), otherwise the raw prediction. This is a
    per-document cache, separate from `_validated_candidate`'s per-person
    lookup: a document is only skipped if that exact `document_id` was
    already processed, regardless of whether any of its destinatarios were
    individually validated before.

    Otherwise (no prior record, or `use_cache=False`), runs the full
    pipeline; if `use_cache`, persists the result keyed by
    `document.document_id` so it can later be looked up when the frontend
    submits a human validation, or returned directly by a future call with
    the same `document_id`.

    Args:
        document (Document): Already-extracted document (see /misc/document-extract).
        session (Session): SQLAlchemy session, used both to look up
            previously-validated destinatarios and to persist this result.
        model (str | None): Ollama model override. Defaults to DEFAULT_MODEL.
        search_backend (SearchBackend | None): Organigram search backend override.
            Defaults to settings.DATA_EXTRACTION_SEARCH_BACKEND.
        hybrid_weight (float | None): Weight given to the embeddings score when
            search_backend="hybrid". Defaults to settings.DATA_EXTRACTION_HYBRID_WEIGHT.
        top_k (int | None): Organigram candidates (per field) used as sector
            evidence. Defaults to settings.DATA_EXTRACTION_TOP_K.
        sector_mode (SectorMode | None): "csv" matches organigram candidates
            against destinatario_por_sector.csv; "hierarchy" reads the
            sector directly off the organigram's own hierarchy instead.
            Defaults to settings.DATA_EXTRACTION_SECTOR_MODE.
        sector_top_k (int | None): Sector-corpus matches considered per
            organigram candidate. Only used when sector_mode="csv". Defaults
            to settings.DATA_EXTRACTION_SECTOR_TOP_K.
        nombre_origen_weight (float | None): Discount applied to nombre-origin
            sector evidence (cargo-origin is always full weight). Defaults to
            settings.DATA_EXTRACTION_NOMBRE_ORIGEN_WEIGHT.
        max_retries (int | None): LLM validation retries override. Defaults to
            DEFAULT_MAX_RETRIES.
        options (dict[str, Any] | None): Ollama chat options override.
        use_cache (bool): Use the DB to retrieve a persisted result for this
            `document_id` (skipping the LLM entirely) and to store the
            result of this run. Defaults to True.

    Returns:
        DataExtractionResult: Extracted recommendation data, with ranked
        sector candidates per destinatario.
    """
    if use_cache:
        existing = data_extraction_get(document.document_id, session)
        if existing:
            return DataExtractionResult.model_validate(
                existing.validation or existing.prediction
            )

    resolved_model = model or DEFAULT_MODEL
    resolved_backend = search_backend or settings.DATA_EXTRACTION_SEARCH_BACKEND
    resolved_hybrid_weight = (
        hybrid_weight
        if hybrid_weight is not None
        else settings.DATA_EXTRACTION_HYBRID_WEIGHT
    )
    resolved_top_k = top_k or settings.DATA_EXTRACTION_TOP_K
    resolved_sector_mode = sector_mode or settings.DATA_EXTRACTION_SECTOR_MODE
    resolved_sector_top_k = sector_top_k or settings.DATA_EXTRACTION_SECTOR_TOP_K
    resolved_nombre_origen_weight = (
        nombre_origen_weight
        if nombre_origen_weight is not None
        else settings.DATA_EXTRACTION_NOMBRE_ORIGEN_WEIGHT
    )
    resolved_max_retries = (
        max_retries if max_retries is not None else DEFAULT_MAX_RETRIES
    )
    resolved_options = {**DEFAULT_OPTIONS, **(options or {})}

    document_text = "\n".join(document.document)

    extraction = await _extract_with_retry(
        document_text,
        model=resolved_model,
        options=resolved_options,
        max_retries=resolved_max_retries,
    )

    destinatarios = [
        _build_destinatario(
            dest,
            backend=resolved_backend,
            top_k=resolved_top_k,
            hybrid_weight=resolved_hybrid_weight,
            sector_mode=resolved_sector_mode,
            sector_top_k=resolved_sector_top_k,
            nombre_origen_weight=resolved_nombre_origen_weight,
            session=session,
        )
        for dest in extraction.destinatarios
    ]

    result = DataExtractionResult(
        numero_recomendacion=extraction.numero_recomendacion,
        fecha_recomendacion=extraction.fecha_recomendacion,
        destinatarios=destinatarios,
        tema=extraction.tema,
        subtema=extraction.subtema,
        datos_personales=extraction.datos_personales,
        contenido_para_publicar=extraction.contenido_para_publicar,
    )

    if use_cache:
        data_extraction_create_or_update(
            data_extraction_id=document.document_id,
            document=document.document,
            prediction=result.model_dump(),
            config={
                "model": resolved_model,
                "search_backend": resolved_backend,
                "hybrid_weight": resolved_hybrid_weight,
                "top_k": resolved_top_k,
                "sector_mode": resolved_sector_mode,
                "sector_top_k": resolved_sector_top_k,
                "nombre_origen_weight": resolved_nombre_origen_weight,
                "max_retries": resolved_max_retries,
                "options": resolved_options,
            },
            session=session,
        )

    return result
