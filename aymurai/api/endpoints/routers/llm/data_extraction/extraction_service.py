from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel, model_validator

from aymurai.api.exceptions import AymuraiAPIException
from aymurai.llm_providers import OllamaLLMProvider
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import Document
from aymurai.settings import settings
from aymurai.utils.yaml_data import load_yaml

from . import organigram_matching
from .schemas import (
    DataExtractionResult,
    DestinatarioExtraction,
    SearchBackend,
    SearchFields,
)

logger = get_logger(__name__)

DEFAULT_MODEL = "gemma4:latest"
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
_TAXONOMY: dict[str, frozenset[str]] = {
    tema: frozenset(subtemas)
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

    taxonomy: ClassVar[dict[str, frozenset[str]]] = _TAXONOMY

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


def _build_destinatario(
    raw: _LLMDestinatario,
    *,
    backend: SearchBackend,
    top_k: int,
    hybrid_weight: float,
    search_fields: SearchFields,
) -> DestinatarioExtraction:
    """
    Cross-reference one destinatario against the organigram and build the public model.

    Args:
        raw (_LLMDestinatario): Destinatario as extracted by the LLM.
        backend (SearchBackend): Organigram search backend to use.
        top_k (int): Max number of candidates to attach.
        hybrid_weight (float): Weight given to the embeddings score when
            backend="hybrid"; ignored otherwise.
        search_fields (SearchFields): Which destinatario field(s) to search:
            "nombre", "cargo", or "both".

    Returns:
        DestinatarioExtraction: Public destinatario with independently ranked
        candidatos_nombre/candidatos_cargo.
    """
    candidatos = organigram_matching.search_candidates(
        nombre=raw.nombre,
        cargo=raw.cargo,
        sector=raw.sector,
        backend=backend,
        top_k=top_k,
        hybrid_weight=hybrid_weight,
        search_fields=search_fields,
    )
    return DestinatarioExtraction(
        nombre=raw.nombre,
        cargo=raw.cargo,
        destinatario_principal=raw.destinatario_principal,
        sector=raw.sector,
        candidatos_nombre=candidatos["nombre"],
        candidatos_cargo=candidatos["cargo"],
    )


async def run_data_extraction(
    document: Document,
    *,
    model: str | None = None,
    search_backend: SearchBackend | None = None,
    hybrid_weight: float | None = None,
    search_fields: SearchFields | None = None,
    top_k: int | None = None,
    max_retries: int | None = None,
    options: dict[str, Any] | None = None,
) -> DataExtractionResult:
    """
    Run the full data-extraction pipeline: LLM extraction + organigram cross-reference.

    Args:
        document (Document): Already-extracted document (see /misc/document-extract).
        model (str | None): Ollama model override. Defaults to DEFAULT_MODEL.
        search_backend (SearchBackend | None): Organigram search backend override.
            Defaults to settings.DATA_EXTRACTION_SEARCH_BACKEND.
        hybrid_weight (float | None): Weight given to the embeddings score when
            search_backend="hybrid". Defaults to settings.DATA_EXTRACTION_HYBRID_WEIGHT.
        search_fields (SearchFields | None): Which destinatario field(s) to
            search: "nombre", "cargo", or "both". Defaults to
            settings.DATA_EXTRACTION_SEARCH_FIELDS.
        top_k (int | None): Candidates per destinatario override. Defaults to
            settings.DATA_EXTRACTION_TOP_K.
        max_retries (int | None): LLM validation retries override. Defaults to
            DEFAULT_MAX_RETRIES.
        options (dict[str, Any] | None): Ollama chat options override.

    Returns:
        DataExtractionResult: Extracted recommendation data, with ranked
        organigram candidates per destinatario.
    """
    resolved_model = model or DEFAULT_MODEL
    resolved_backend = search_backend or settings.DATA_EXTRACTION_SEARCH_BACKEND
    resolved_hybrid_weight = (
        hybrid_weight
        if hybrid_weight is not None
        else settings.DATA_EXTRACTION_HYBRID_WEIGHT
    )
    resolved_search_fields = search_fields or settings.DATA_EXTRACTION_SEARCH_FIELDS
    resolved_top_k = top_k or settings.DATA_EXTRACTION_TOP_K
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
            search_fields=resolved_search_fields,
        )
        for dest in extraction.destinatarios
    ]

    return DataExtractionResult(
        numero_recomendacion=extraction.numero_recomendacion,
        fecha_recomendacion=extraction.fecha_recomendacion,
        destinatarios=destinatarios,
        tema=extraction.tema,
        subtema=extraction.subtema,
        datos_personales=extraction.datos_personales,
        contenido_para_publicar=extraction.contenido_para_publicar,
    )
