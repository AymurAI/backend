from __future__ import annotations

from typing import Iterator

import ollama

from aymurai.llm_providers.provider import LLMProvider, LLMResponse


class OllamaLLMProvider(LLMProvider):
    """Adapter that wraps `ollama.chat` preserving the common interface."""

    def __init__(
        self,
        model: str,
        *,
        system_prompt: str | None = None,
        keep_alive: int | str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(model=model, **kwargs)
        self.system_prompt = system_prompt
        self.keep_alive = keep_alive

    def generate(
        self,
        prompt: str | None = None,
        *,
        messages: list[dict[str, str]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        # Build the message payload
        payload = self._build_messages(prompt=prompt, messages=messages)

        # Call ollama.chat
        response = ollama.chat(
            model=self.model_name,
            messages=payload,
            keep_alive=self.keep_alive,
            **kwargs,
        )

        # Extract text and metadata
        text = response.get("message", {}).get("content", "")
        metadata = {
            "model": self.model_name,
            "provider": "ollama",
            "eval_count": response.get("eval_count"),
            "eval_duration": response.get("eval_duration"),
        }

        return LLMResponse(text=text, metadata=metadata, raw=response)

    def stream(
        self,
        prompt: str | None = None,
        *,
        messages: list[dict[str, str]] | None = None,
        **kwargs,
    ) -> Iterator[LLMResponse]:
        # Build the message payload
        payload = self._build_messages(prompt=prompt, messages=messages)

        # Call ollama.chat with streaming enabled
        stream_kwargs = {**kwargs, "stream": True}

        # Iterate over the streamed responses
        for chunk in ollama.chat(
            model=self.model_name,
            messages=payload,
            keep_alive=self.keep_alive,
            **stream_kwargs,
        ):
            # Extract text and metadata from each chunk
            text = chunk.get("message", {}).get("content", "")
            metadata = {
                "model": self.model_name,
                "provider": "ollama",
                "done": chunk.get("done"),
            }

            yield LLMResponse(text=text, metadata=metadata, raw=chunk)

    def _build_messages(
        self,
        *,
        prompt: str | None,
        messages: list[dict[str, str]] | None = None,
    ) -> list[dict[str, str]]:
        """
        Build the message payload for `ollama.chat`.

        Args:
            prompt (str | None): The user prompt to be sent to the model.
            messages (list[dict[str, str]] | None, optional): A list of message dictionaries to be sent to the model.
                Defaults to None.

        Raises:
            ValueError: If neither prompt nor messages are provided.

        Returns:
            list[dict[str, str]]: The message payload to be sent to `ollama.chat`.
        """
        if messages is not None:
            return list(messages)

        if prompt is None:
            raise ValueError("Either prompt or messages must be provided.")

        payload: list[dict[str, str]] = []

        if self.system_prompt:
            payload.append({"role": "system", "content": self.system_prompt})

        payload.append({"role": "user", "content": prompt})

        return payload


__all__ = ["OllamaLLMProvider"]
