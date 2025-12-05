from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator

import tiktoken
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from aymurai.llm_providers import OllamaLLMProvider
from aymurai.logger import get_logger
from aymurai.settings import settings
from aymurai.utils.yaml_data import load_yaml

logger = get_logger(__name__)

router = APIRouter()

DEFAULT_MODEL = "gpt-oss:20b"
DEFAULT_OPTIONS = {"num_ctx": 16_384, "num_predict": 4096}
DEFAULT_TOKENIZER = "o200k_harmony"
PROMPT_TEMPLATE_PATH = Path(settings.RESOURCES_BASEPATH) / "llm" / "summarization.yml"


def _load_prompt_defaults(path: Path) -> tuple[str, str]:
    """
    Load default placeholders from the YAML template,
    ensuring both required fields are present.

    Args:
        path: Path to the summarization YAML file.

    Returns:
        tuple[str, str]: Defaults for `information_to_extract` and `entities_to_identify`.

    Raises:
        FileNotFoundError: If the YAML file cannot be located.
        RuntimeError: If the defaults block is missing or incomplete.
    """
    content = load_yaml(str(path))
    defaults = content.get("defaults", {})
    info = (defaults.get("information-to-extract") or "").strip()
    entities = (defaults.get("entities-to-identify") or "").strip()
    if not info or not entities:
        raise RuntimeError("summarization defaults missing in YAML")
    return info, entities


DEFAULT_INFORMATION_TO_EXTRACT, DEFAULT_ENTITIES_TO_IDENTIFY = _load_prompt_defaults(
    PROMPT_TEMPLATE_PATH
)


class SummarizationRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Texto de entrada a resumir.",
                "model": DEFAULT_MODEL,
                "tokenizer": DEFAULT_TOKENIZER,
                "options": DEFAULT_OPTIONS,
            }
        }
    )

    text: str = Field(..., description="Raw document to summarize.")
    model: str = Field(
        default=DEFAULT_MODEL,
        description="Model name for Ollama. Defaults to gpt-oss:20b.",
    )
    tokenizer: str | None = Field(
        default=DEFAULT_TOKENIZER,
        description="Tokenizer name (tiktoken). Falls back to whitespace if unavailable.",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Optional system prompt override. Defaults to the template in /resources/llm/summarization.yml.",
    )
    information_to_extract: str | None = Field(
        default=DEFAULT_INFORMATION_TO_EXTRACT,
        description="Template variable information_to_extract.",
    )
    entities_to_identify: str | None = Field(
        default=DEFAULT_ENTITIES_TO_IDENTIFY,
        description="Template variable entities_to_identify.",
    )
    options: dict[str, Any] = Field(
        default_factory=lambda: DEFAULT_OPTIONS.copy(),
        description="Ollama chat options. Defaults to num_ctx=16_384 and num_predict=4096.",
    )


class SummarizationStep(BaseModel):
    chunk_index: int
    input_tokens: int
    source: str


class SummarizationResponse(BaseModel):
    summary: str
    model: str
    system_prompt: str
    options: dict[str, Any]
    chunks_used: int
    steps: list[SummarizationStep]


def _load_template_prompt(
    *,
    information_to_extract: str | None,
    entities_to_identify: str | None,
) -> str:
    """
    Load and format the summarization prompt template.

    Args:
        information_to_extract: Template placeholder describing what to extract.
        entities_to_identify: Template placeholder listing entities to detect.

    Returns:
        str: Formatted system prompt for summarization.

    Raises:
        HTTPException: If the template file is missing or cannot be parsed.
    """
    path = PROMPT_TEMPLATE_PATH
    try:
        content = load_yaml(str(path))
        template = content["system-prompts"]["template"]

    except FileNotFoundError as exc:
        logger.exception(f"Summarization prompt template not found at {path}")
        raise HTTPException(
            status_code=500,
            detail="Summarization prompt template not found.",
        ) from exc
    except Exception as exc:
        logger.exception("Error loading summarization prompt template.")
        raise HTTPException(
            status_code=500,
            detail="Unable to load summarization prompt template.",
        ) from exc

    info = information_to_extract or DEFAULT_INFORMATION_TO_EXTRACT
    entities = entities_to_identify or DEFAULT_ENTITIES_TO_IDENTIFY

    return template.format(
        information_to_extract=info,
        entities_to_identify=entities,
    )


def _load_tokenizer(tokenizer_name: str | None) -> tiktoken.Encoding | None:
    """
    Load a tiktoken tokenizer by name.

    Args:
        tokenizer_name (str | None): Name of the tokenizer to load.

    Returns:
        tiktoken.Encoding | None: The loaded tokenizer encoding or None if unavailable.
    """
    if not tokenizer_name:
        return None

    try:
        return tiktoken.get_encoding(tokenizer_name)

    except Exception:
        logger.warning(
            f"Tokenizer {tokenizer_name} is not available. Falling back to whitespace."
        )
        return None


def _count_tokens(text: str, tokenizer: Any) -> int:
    """
    Count the number of tokens in the given text using the provided tokenizer.

    Args:
        text (str): The input text to count tokens for.
        tokenizer (Any): The tokenizer to use for counting tokens.

    Returns:
        int: The number of tokens in the input text.
    """
    if tokenizer is None:
        return len(text.split())
    try:
        return len(tokenizer.encode(text))
    except Exception:
        return len(text.split())


def _build_provider(
    model_name: str,
    *,
    tokenizer_name: str | None,
    system_prompt: str,
    context_limit: int,
) -> OllamaLLMProvider:
    """
    Build an Ollama provider, adjusting available context for the system prompt.

    Args:
        model_name: Name of the model to use.
        tokenizer_name: Tokenizer name to attempt loading.
        system_prompt: System prompt to set and budget for.
        context_limit: Maximum number of context tokens.

    Returns:
        OllamaLLMProvider: Configured OllamaLLMProvider instance.
    """
    encoding = _load_tokenizer(tokenizer_name)
    available_context = max(context_limit - _count_tokens(system_prompt, encoding), 1)

    return OllamaLLMProvider(
        model=model_name,
        tokenizer=encoding,
        system_prompt=system_prompt,
        max_context_tokens=available_context,
    )


async def _summarize_once(
    provider: OllamaLLMProvider,
    *,
    text: str,
    options: dict[str, Any],
) -> str:
    """
    Run a single summarization call on the provider.

    Args:
        provider: Initialized OllamaLLMProvider instance.
        text: Chunk or combined text to summarize.
        options: Provider options forwarded to the model.

    Returns:
        str: The model's text output for the given input.
    """
    response = await provider.async_generate(prompt=text, options=options)
    return response.text


async def _rolling_summarize(
    provider: OllamaLLMProvider,
    *,
    text: str,
    options: dict[str, Any],
) -> tuple[str, list[SummarizationStep], int]:
    """
    Summarize potentially long text by chunking and rolling summaries forward.

    Args:
        provider: Initialized OllamaLLMProvider instance.
        text: Full document text to summarize.
        options: Provider options forwarded to the model.

    Returns:
        tuple[str, list[SummarizationStep], int]: A tuple of (final_summary, steps_metadata, chunk_count).
    """
    chunks = provider.chunk_text(text, max_tokens=provider.max_context_tokens)
    if not chunks:
        return "", [], 0

    steps = []
    summary = await _summarize_once(provider, text=chunks[0].text, options=options)
    steps.append(
        SummarizationStep(
            chunk_index=chunks[0].index,
            input_tokens=chunks[0].token_count,
            source="chunk",
        )
    )

    for chunk in chunks[1:]:
        combined_text = f"{summary}\n\n{chunk.text}"
        combined_tokens = provider.count_tokens(combined_text)

        if (
            provider.max_context_tokens
            and combined_tokens > provider.max_context_tokens
        ):
            chunk_summary = await _summarize_once(
                provider,
                text=chunk.text,
                options=options,
            )
            steps.append(
                SummarizationStep(
                    chunk_index=chunk.index,
                    input_tokens=chunk.token_count,
                    source="chunk",
                )
            )
            combined_text = f"{summary}\n\n{chunk_summary}"
            combined_tokens = provider.count_tokens(combined_text)

            if (
                provider.max_context_tokens
                and combined_tokens > provider.max_context_tokens
            ):
                trimmed_parts = []
                for part in provider.chunk_text(
                    combined_text, max_tokens=provider.max_context_tokens
                ):
                    tentative = " ".join(trimmed_parts + [part.text])
                    if (
                        provider.max_context_tokens
                        and provider.count_tokens(tentative)
                        > provider.max_context_tokens
                    ):
                        break
                    trimmed_parts.append(part.text)
                combined_text = " ".join(trimmed_parts)
                combined_tokens = provider.count_tokens(combined_text)

        summary = await _summarize_once(
            provider,
            text=combined_text,
            options=options,
        )
        steps.append(
            SummarizationStep(
                chunk_index=chunk.index,
                input_tokens=combined_tokens,
                source="summary+chunk",
            )
        )

    return summary, steps, len(chunks)


def _build_sse_message(payload: dict[str, Any]) -> str:
    """
    Format a payload as an SSE data message.

    Args:
        payload: Dictionary to serialize into the SSE data field.

    Returns:
        str: Serialized SSE message string.
    """
    return f"data: {json.dumps(payload)}\n\n"


def _trim_to_context(provider: OllamaLLMProvider, text: str) -> str:
    """
    Trim combined text to respect the provider's context window.

    Args:
        provider: Provider with a configured max_context_tokens.
        text: Concatenated summary and chunk text.

    Returns:
        str: Text trimmed to fit within the context limit.
    """
    if not provider.max_context_tokens:
        return text

    trimmed_parts: list[str] = []
    for part in provider.chunk_text(text, max_tokens=provider.max_context_tokens):
        tentative = " ".join(trimmed_parts + [part.text])
        if (
            provider.max_context_tokens
            and provider.count_tokens(tentative) > provider.max_context_tokens
        ):
            break
        trimmed_parts.append(part.text)

    return " ".join(trimmed_parts)


@router.post("/summarize", response_model=SummarizationResponse)
async def summarize_document(payload: SummarizationRequest) -> SummarizationResponse:
    """
    Summarize a document using a local Ollama model.

    The endpoint chunks inputs above the context limit and performs a rolling
    summarization that keeps the interim summary in context for subsequent chunks.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty.")

    system_prompt = payload.system_prompt or _load_template_prompt(
        information_to_extract=payload.information_to_extract,
        entities_to_identify=payload.entities_to_identify,
    )
    model_name = payload.model or DEFAULT_MODEL
    options = {**DEFAULT_OPTIONS, **(payload.options or {})}

    try:
        context_limit = int(options.get("num_ctx", DEFAULT_OPTIONS["num_ctx"]))

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="num_ctx option must be an integer.",
        ) from exc

    if context_limit <= 0:
        raise HTTPException(status_code=400, detail="num_ctx must be greater than 0.")

    provider = _build_provider(
        model_name,
        tokenizer_name=payload.tokenizer,
        system_prompt=system_prompt,
        context_limit=context_limit,
    )

    summary, steps, chunk_count = await _rolling_summarize(
        provider,
        text=payload.text,
        options=options,
    )

    return SummarizationResponse(
        summary=summary,
        model=provider.model_name,
        system_prompt=system_prompt,
        options=options,
        chunks_used=chunk_count or 1,
        steps=steps,
    )


@router.post("/summarize/stream")
async def stream_summarize_document(
    payload: SummarizationRequest,
) -> StreamingResponse:
    """
    Stream a document summary using server-sent events (text/event-stream).

    Emits:
        - data: {"type": "meta", ...}
        - data: {"type": "token", "chunk_index": int, "source": str, "text": str}
        - data: {"type": "summary", "summary": str, "chunks_used": int, "steps": [...], "model": str}
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty.")

    system_prompt = payload.system_prompt or _load_template_prompt(
        information_to_extract=payload.information_to_extract,
        entities_to_identify=payload.entities_to_identify,
    )
    model_name = payload.model or DEFAULT_MODEL
    options = {**DEFAULT_OPTIONS, **(payload.options or {})}

    try:
        context_limit = int(options.get("num_ctx", DEFAULT_OPTIONS["num_ctx"]))

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="num_ctx option must be an integer.",
        ) from exc

    if context_limit <= 0:
        raise HTTPException(status_code=400, detail="num_ctx must be greater than 0.")

    provider = _build_provider(
        model_name,
        tokenizer_name=payload.tokenizer,
        system_prompt=system_prompt,
        context_limit=context_limit,
    )

    async def event_stream() -> AsyncIterator[str]:
        yield _build_sse_message(
            {
                "type": "meta",
                "model": provider.model_name,
                "system_prompt": system_prompt,
                "options": options,
            }
        )

        chunks = provider.chunk_text(
            payload.text,
            max_tokens=provider.max_context_tokens,
        )

        if not chunks:
            yield _build_sse_message(
                {
                    "type": "summary",
                    "summary": "",
                    "chunks_used": 0,
                    "steps": [],
                    "model": provider.model_name,
                }
            )
            return

        steps: list[dict[str, Any]] = []
        summary = ""

        for chunk in chunks:
            source = "chunk" if not summary else "summary+chunk"
            combined_text = f"{summary}\n\n{chunk.text}" if summary else chunk.text
            combined_tokens = provider.count_tokens(combined_text)

            if (
                provider.max_context_tokens
                and combined_tokens > provider.max_context_tokens
                and summary
            ):
                # Summarize the current chunk alone when the combined context would overflow.
                chunk_summary = ""
                async for resp in provider.async_stream(
                    prompt=chunk.text,
                    options=options,
                ):
                    token = resp.text
                    if not token:
                        continue
                    chunk_summary += token
                    yield _build_sse_message(
                        {
                            "type": "token",
                            "chunk_index": chunk.index,
                            "source": "chunk",
                            "text": token,
                        }
                    )

                steps.append(
                    {
                        "chunk_index": chunk.index,
                        "input_tokens": chunk.token_count,
                        "source": "chunk",
                    }
                )

                combined_text = f"{summary}\n\n{chunk_summary}"
                combined_text = _trim_to_context(provider, combined_text)
                source = "summary+chunk"
                combined_tokens = provider.count_tokens(combined_text)

            updated_summary = ""
            async for resp in provider.async_stream(
                prompt=combined_text,
                options=options,
            ):
                token = resp.text
                if not token:
                    continue
                updated_summary += token
                yield _build_sse_message(
                    {
                        "type": "token",
                        "chunk_index": chunk.index,
                        "source": source,
                        "text": token,
                    }
                )

            steps.append(
                {
                    "chunk_index": chunk.index,
                    "input_tokens": combined_tokens,
                    "source": source,
                }
            )
            summary = updated_summary

        yield _build_sse_message(
            {
                "type": "summary",
                "summary": summary,
                "chunks_used": len(chunks),
                "steps": steps,
                "model": provider.model_name,
            }
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
