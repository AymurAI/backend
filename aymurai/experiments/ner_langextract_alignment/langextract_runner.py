from __future__ import annotations

import os
import time
import uuid
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import langextract as lx
import mlflow
import requests
from langextract.core import data as lx_data
from langextract.providers.openai import OpenAILanguageModel
from mlflow.entities import SpanStatusCode

from aymurai.experiments.ner_langextract_alignment.config import LangExtractConfig
from aymurai.experiments.ner_langextract_alignment.types import LLMTrace
from aymurai.logger import get_logger
from aymurai.utils.openai_httpx_compat import apply_openai_httpx_compat
from aymurai.utils.yaml_data import load_yaml

logger = get_logger(__name__)


def _current_mlflow_trace_id() -> str | None:
    try:
        active_span = mlflow.get_current_active_span()
    except Exception:
        return None

    if active_span is None:
        return None

    for attr_name in ("request_id", "trace_id"):
        value = getattr(active_span, attr_name, None)
        if isinstance(value, str) and value:
            return value

    return None


class TracingOpenAIModel(OpenAILanguageModel):
    """OpenAI-compatible model that captures raw prompt/output traces."""

    def __init__(self, *args, **kwargs) -> None:
        self.max_tokens = kwargs.pop("max_tokens", None)
        self.request_timeout_s = kwargs.pop("request_timeout_s", None)
        self.think = bool(kwargs.pop("think", False))
        super().__init__(*args, **kwargs)
        self.captured_traces: list[dict[str, Any]] = []

    def reset_traces(self) -> None:
        self.captured_traces.clear()

    def _token_limit_param_name(self) -> str:
        """
        Select token limit parameter compatible with the target model family.
        GPT-5 chat-completions requires `max_completion_tokens`.
        """
        model_id = str(self.model_id or "").lower()
        if model_id.startswith("gpt-5"):
            return "max_completion_tokens"
        return "max_tokens"

    def _should_force_json_response(self) -> bool:
        model_id = str(self.model_id or "").lower()
        return model_id.startswith("gpt-")

    def _is_ollama_endpoint(self) -> bool:
        base_url = str(self.base_url or "").lower()
        return "localhost:11434" in base_url or "127.0.0.1:11434" in base_url

    def _ollama_chat_url(self) -> str:
        parsed = urlsplit(str(self.base_url or "http://localhost:11434/v1"))
        path = parsed.path or ""
        if path.endswith("/v1"):
            path = path[: -len("/v1")]
        path = f"{path.rstrip('/')}/api/chat"
        return urlunsplit((parsed.scheme or "http", parsed.netloc, path, "", ""))

    def _call_ollama_chat(
        self, *, prompt: str, temperature: float | None, max_tokens: int | None
    ) -> tuple[str, dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "think": bool(self.think),
            "stream": False,
        }
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = float(temperature)
        if max_tokens is not None:
            options["num_predict"] = int(max_tokens)
        if options:
            payload["options"] = options

        timeout = float(self.request_timeout_s) if self.request_timeout_s else None
        response = requests.post(self._ollama_chat_url(), json=payload, timeout=timeout)
        response.raise_for_status()
        parsed = response.json()
        message = parsed.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Empty or invalid Ollama content in response.")
        metadata = {}
        input_tokens = parsed.get("prompt_eval_count")
        output_tokens = parsed.get("eval_count")
        if isinstance(input_tokens, int):
            metadata["token_input"] = input_tokens
        if isinstance(output_tokens, int):
            metadata["token_output"] = output_tokens
        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
            metadata["token_total"] = input_tokens + output_tokens
        thinking = message.get("thinking")
        if thinking is not None:
            metadata["thinking"] = thinking
        return content, metadata

    def _extract_openai_usage(self, response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}

        def _safe_int(v: Any) -> int | None:
            try:
                if v is None:
                    return None
                return int(v)
            except Exception:
                return None

        # openai-python objects may expose attrs and/or dict-like `usage`.
        prompt_tokens = _safe_int(getattr(usage, "prompt_tokens", None))
        completion_tokens = _safe_int(getattr(usage, "completion_tokens", None))
        total_tokens = _safe_int(getattr(usage, "total_tokens", None))

        if hasattr(usage, "get"):
            prompt_tokens = (
                prompt_tokens
                if prompt_tokens is not None
                else _safe_int(usage.get("prompt_tokens"))
            )
            completion_tokens = (
                completion_tokens
                if completion_tokens is not None
                else _safe_int(usage.get("completion_tokens"))
            )
            total_tokens = (
                total_tokens
                if total_tokens is not None
                else _safe_int(usage.get("total_tokens"))
            )

        out: dict[str, int] = {}
        if prompt_tokens is not None:
            out["token_input"] = prompt_tokens
        if completion_tokens is not None:
            out["token_output"] = completion_tokens
        if total_tokens is not None:
            out["token_total"] = total_tokens
        elif prompt_tokens is not None and completion_tokens is not None:
            out["token_total"] = prompt_tokens + completion_tokens
        return out

    @mlflow.trace(name="langextract.openai_single_prompt", span_type="LLM")
    def _process_single_prompt(self, prompt: str, config: dict):
        trace_id = _current_mlflow_trace_id() or uuid.uuid4().hex
        started = time.perf_counter()
        temperature = config.get("temperature", self.temperature)
        max_tokens = config.get("max_tokens", self.max_tokens)
        try:
            with mlflow.start_span(
                name="langextract.openai_client_call",
                span_type="LLM",
                attributes={
                    "model_id": self.model_id,
                    "provider": "openai_compatible",
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            ):
                api_params = {
                    "model": self.model_id,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an extraction engine. Respond with valid JSON only.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                }
                extra_metadata: dict[str, Any] = {}
                if self.think and self._is_ollama_endpoint():
                    output_text, extra_metadata = self._call_ollama_chat(
                        prompt=prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                else:
                    if temperature is not None:
                        api_params["temperature"] = temperature
                    if max_tokens is not None:
                        api_params[self._token_limit_param_name()] = max_tokens
                    if self.request_timeout_s is not None:
                        api_params["timeout"] = float(self.request_timeout_s)
                    if self._should_force_json_response():
                        api_params["response_format"] = {"type": "json_object"}

                    response = self._client.chat.completions.create(**api_params)
                    extra_metadata.update(self._extract_openai_usage(response))
                    output_text = response.choices[0].message.content
                response = lx.core.types.ScoredOutput(score=1.0, output=output_text)
            duration_ms = (time.perf_counter() - started) * 1000.0
            self.captured_traces.append(
                {
                    "trace_id": trace_id,
                    "prompt": prompt,
                    "raw_output": response.output,
                    "duration_ms": duration_ms,
                    "error": None,
                    "metadata": {
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "think": self.think,
                        **extra_metadata,
                    },
                }
            )
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000.0
            self.captured_traces.append(
                {
                    "trace_id": trace_id,
                    "prompt": prompt,
                    "raw_output": None,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                    "metadata": {
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "think": self.think,
                    },
                }
            )
            raise lx.exceptions.InferenceRuntimeError(
                f"Custom OpenAI API error: {exc}", original=exc
            ) from exc


def load_examples_from_yaml(path: str) -> list[lx_data.ExampleData]:
    payload = load_yaml(path)
    examples_data = payload.get("examples", []) if isinstance(payload, dict) else []
    examples: list[lx_data.ExampleData] = []

    for item in examples_data:
        text = str(item.get("text", ""))
        exts = []
        for ext in item.get("extractions", []):
            exts.append(
                lx_data.Extraction(
                    extraction_class=str(ext["extraction_class"]),
                    extraction_text=str(ext["extraction_text"]),
                )
            )
        examples.append(lx_data.ExampleData(text=text, extractions=exts))

    return examples


def build_tracing_model(config: LangExtractConfig) -> TracingOpenAIModel:
    apply_openai_httpx_compat()
    api_key = os.getenv(config.api_key_env, config.api_key_fallback)
    return TracingOpenAIModel(
        model_id=config.model_id,
        api_key=api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        think=config.think,
        request_timeout_s=config.request_timeout_s,
        max_workers=config.max_workers,
    )


def extraction_to_dict(extraction: lx_data.Extraction) -> dict[str, Any]:
    result = {
        "extraction_class": extraction.extraction_class,
        "extraction_text": extraction.extraction_text,
        "alignment_status": (
            extraction.alignment_status.value if extraction.alignment_status else None
        ),
        "char_interval": None,
        "attributes": extraction.attributes or {},
    }

    if extraction.char_interval:
        result["char_interval"] = {
            "start_pos": extraction.char_interval.start_pos,
            "end_pos": extraction.char_interval.end_pos,
        }

    return result


def annotated_document_to_dict(doc: lx_data.AnnotatedDocument) -> dict[str, Any]:
    return {
        "document_id": doc.document_id,
        "text": doc.text,
        "extractions": [extraction_to_dict(ext) for ext in (doc.extractions or [])],
    }


@mlflow.trace(name="langextract.extract_document", span_type="CHAIN")
def run_langextract(
    *,
    sample_id: str,
    text: str,
    config: LangExtractConfig,
    examples: list[lx_data.ExampleData],
    model: TracingOpenAIModel,
) -> tuple[dict[str, Any], list[LLMTrace], float]:
    started = time.perf_counter()
    sanitized_text = str(text or "").replace("\x00", "").strip()
    attempts_total = max(1, int(config.retries) + 1)
    retry_backoff_s = max(0.0, float(config.retry_backoff_s))
    sample_trace_id = _current_mlflow_trace_id() or uuid.uuid4().hex

    if not sanitized_text:
        empty_output = {
            "document_id": sample_id,
            "text": text,
            "extractions": [],
            "error": "empty_or_invalid_input",
        }
        trace = LLMTrace(
            trace_id=sample_trace_id,
            sample_id=sample_id,
            provider=config.provider,
            model=config.model_id,
            prompt="",
            input_text=text,
            raw_output=None,
            parsed_output=empty_output,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            error="empty_or_invalid_input",
            metadata={"skipped_inference": True},
        )
        return empty_output, [trace], (time.perf_counter() - started) * 1000.0

    try:
        active_span = mlflow.get_current_active_span()
        if active_span is not None:
            mlflow.update_current_trace(
                tags={
                    "sample_id": sample_id,
                    "provider": config.provider,
                    "model_id": config.model_id,
                }
            )
    except Exception:
        # Keep extraction resilient if tracing backend is unavailable.
        pass

    result = None
    last_exc: Exception | None = None
    captured_traces: list[dict[str, Any]] = []
    failed_output: dict[str, Any] | None = None

    with mlflow.start_span(
        name="langextract.extract_call",
        span_type="CHAIN",
        attributes={
            "sample_id": sample_id,
            "retry_attempts": attempts_total,
            "extraction_passes": config.extraction_passes,
            "batch_length": config.batch_length,
            "max_workers": config.max_workers,
            "examples_count": len(examples),
        },
    ) as span:
        logger.info(
            "langextract start: sample_id=%s text_chars=%s attempts=%s timeout_s=%s",
            sample_id,
            len(sanitized_text),
            attempts_total,
            getattr(config, "request_timeout_s", None),
        )
        span.set_inputs(
            {
                "text": sanitized_text,
                "prompt_description": config.prompt_description,
            }
        )
        for attempt in range(1, attempts_total + 1):
            model.reset_traces()
            try:
                result = lx.extract(
                    text_or_documents=sanitized_text,
                    prompt_description=config.prompt_description,
                    examples=examples,
                    model=model,
                    use_schema_constraints=False,
                    extraction_passes=config.extraction_passes,
                    batch_length=config.batch_length,
                    max_workers=config.max_workers,
                    show_progress=False,
                )
                captured_traces.extend(model.captured_traces)
                span.set_attribute("retry_attempt_used", attempt)
                logger.info(
                    "langextract success: sample_id=%s attempt=%s/%s elapsed_ms=%.2f",
                    sample_id,
                    attempt,
                    attempts_total,
                    (time.perf_counter() - started) * 1000.0,
                )
                break
            except Exception as exc:
                captured_traces.extend(model.captured_traces)
                last_exc = exc
                logger.warning(
                    "langextract extraction failed (sample_id=%s attempt=%s/%s): %s",
                    sample_id,
                    attempt,
                    attempts_total,
                    exc,
                )
                if attempt < attempts_total and retry_backoff_s > 0:
                    time.sleep(retry_backoff_s * attempt)

        if result is None:
            failed_output = {
                "document_id": sample_id,
                "text": text,
                "extractions": [],
                "error": str(last_exc) if last_exc else "langextract_unknown_error",
            }
            try:
                span.set_outputs(failed_output)
                span.set_attribute("retry_attempt_used", attempts_total)
                span.set_attribute("failed_after_retries", True)
                span.set_status(SpanStatusCode.ERROR)
            except Exception:
                pass

    elapsed_ms = (time.perf_counter() - started) * 1000.0

    if failed_output is not None:
        try:
            active_span = mlflow.get_current_active_span()
            if active_span is not None:
                active_span.set_status(SpanStatusCode.ERROR)
                active_span.set_attribute("failed_after_retries", True)
        except Exception:
            pass

        traces: list[LLMTrace] = []
        for raw in captured_traces:
            traces.append(
                LLMTrace(
                    trace_id=raw.get("trace_id", sample_trace_id),
                    sample_id=sample_id,
                    provider=config.provider,
                    model=config.model_id,
                    prompt=raw.get("prompt", ""),
                    input_text=sanitized_text,
                    raw_output=raw.get("raw_output"),
                    parsed_output=failed_output,
                    duration_ms=float(raw.get("duration_ms", 0.0)),
                    error=raw.get("error") or failed_output["error"],
                    metadata={
                        **(raw.get("metadata") or {}),
                        "fallback_empty_extractions": True,
                    },
                )
            )

        if not traces:
            traces.append(
                LLMTrace(
                    trace_id=sample_trace_id,
                    sample_id=sample_id,
                    provider=config.provider,
                    model=config.model_id,
                    prompt="",
                    input_text=sanitized_text,
                    raw_output=None,
                    parsed_output=failed_output,
                    duration_ms=elapsed_ms,
                    error=failed_output["error"],
                    metadata={
                        "retry_attempt_used": attempts_total,
                        "fallback_empty_extractions": True,
                    },
                )
            )

        return failed_output, traces, elapsed_ms

    if isinstance(result, list):
        annotated_doc = result[0]
    else:
        annotated_doc = result

    traces: list[LLMTrace] = []
    parsed_output = annotated_document_to_dict(annotated_doc)
    try:
        span.set_outputs(parsed_output)
    except Exception:
        pass

    for raw in captured_traces:
        traces.append(
            LLMTrace(
                trace_id=raw.get("trace_id", sample_trace_id),
                sample_id=sample_id,
                provider=config.provider,
                model=config.model_id,
                prompt=raw["prompt"],
                input_text=sanitized_text,
                raw_output=raw.get("raw_output"),
                parsed_output=parsed_output,
                duration_ms=float(raw.get("duration_ms", 0.0)),
                error=raw.get("error"),
                metadata=raw.get("metadata") or {},
            )
        )

    return parsed_output, traces, elapsed_ms
