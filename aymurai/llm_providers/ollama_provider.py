from __future__ import annotations

from typing import Any, AsyncIterator, Iterator

import ollama
from ollama import AsyncClient

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
        self._async_client: AsyncClient | None = None

    def generate(
        self,
        prompt: str | None = None,
        *,
        messages: list[dict[str, str]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Generate text using the configured Ollama model.

        Args:
            prompt (str | None, optional): Optional single prompt string to be transformed into a chat message. Defaults to None.
            messages (list[dict[str, str]] | None, optional): Optional list of pre-formatted chat messages to send. Defaults to None.

        Returns:
            LLMResponse: Response containing the generated text, metadata about the request, and the raw payload.
        """
        # Build the message payload
        payload = self._build_messages(prompt=prompt, messages=messages)

        # Call ollama.chat
        response = ollama.chat(
            model=self.model_name,
            messages=payload,
            keep_alive=self.keep_alive,
            **kwargs,
        )

        return self._build_llm_response(
            response,
            extra_metadata={
                "eval_count": response.get("eval_count"),
                "eval_duration": response.get("eval_duration"),
            },
        )

    async def async_generate(
        self,
        prompt: str | None = None,
        *,
        messages: list[dict[str, str]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Asynchronously generate text using the configured Ollama model.

        Args:
            prompt (str | None): Optional single prompt string to be transformed into a chat message. Defaults to None.
            messages (list[dict[str, str]] | None): Optional list of pre-formatted chat messages to send. Defaults to None.
            **kwargs: Additional keyword arguments forwarded to the Ollama AsyncClient chat endpoint.

        Returns:
            LLMResponse: Response containing the generated text, metadata about the request, and the raw payload.
        """
        # Build the message payload
        payload = self._build_messages(prompt=prompt, messages=messages)

        # Call ollama.chat asynchronously
        client = self._get_async_client()
        response = await client.chat(
            model=self.model_name,
            messages=payload,
            keep_alive=self.keep_alive,
            **kwargs,
        )

        return self._build_llm_response(
            response,
            extra_metadata={
                "eval_count": response.get("eval_count"),
                "eval_duration": response.get("eval_duration"),
            },
        )

    def stream(
        self,
        prompt: str | None = None,
        *,
        messages: list[dict[str, str]] | None = None,
        **kwargs,
    ) -> Iterator[LLMResponse]:
        """
        Stream the response from the model using the provided prompt or messages.

        Args:
            prompt (str | None, optional): Optional single prompt string to be transformed into a chat message. Defaults to None.
            messages (list[dict[str, str]] | None, optional): Optional list of pre-formatted chat messages to send. Defaults to None.

        Yields:
            Iterator[LLMResponse]: Response chunks containing generated text, metadata, and raw payloads.
        """
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
            yield self._build_stream_response(chunk)

    async def async_stream(
        self,
        prompt: str | None = None,
        *,
        messages: list[dict[str, str]] | None = None,
        **kwargs,
    ) -> AsyncIterator[LLMResponse]:
        """
        Asynchronously stream the response from the model using the provided prompt or messages.

        Args:
            prompt (str | None, optional): Optional single prompt string to be transformed into a chat message. Defaults to None.
            messages (list[dict[str, str]] | None, optional): Optional list of pre-formatted chat messages to send. Defaults to None.

        Yields:
            AsyncIterator[LLMResponse]: Asynchronous iterator yielding response chunks containing generated text, metadata, and raw payloads.
        """
        # Build the message payload
        payload = self._build_messages(prompt=prompt, messages=messages)

        # Call ollama.chat with streaming enabled
        stream_kwargs = {**kwargs, "stream": True}

        # Iterate over the streamed responses asynchronously
        client = self._get_async_client()
        async for chunk in await client.chat(
            model=self.model_name,
            messages=payload,
            keep_alive=self.keep_alive,
            **stream_kwargs,
        ):
            yield self._build_stream_response(chunk)

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

        payload = []

        if self.system_prompt:
            payload.append({"role": "system", "content": self.system_prompt})

        payload.append({"role": "user", "content": prompt})

        return payload

    def _get_async_client(self) -> AsyncClient:
        """
        Lazily instantiate and reuse an AsyncClient instance.

        Returns:
            AsyncClient: The AsyncClient instance for making asynchronous requests.
        """
        if self._async_client is None:
            self._async_client = AsyncClient()
        return self._async_client

    def _build_llm_response(
        self, response: dict[str, Any], *, extra_metadata: dict[str, Any] | None = None
    ) -> LLMResponse:
        """
        Build an LLMResponse with consistent metadata from the response payload.

        Args:
            response (dict[str, Any]): The response payload from the Ollama model.
            extra_metadata (dict[str, Any] | None, optional): Additional metadata to include in the response. Defaults to None.

        Returns:
            LLMResponse: The constructed LLMResponse object containing text, metadata, and raw response.
        """
        # Extract the generated text
        text = response.get("message", {}).get("content", "")

        # Build metadata
        metadata = {
            "model": self.model_name,
            "provider": "ollama",
        }

        # Include any extra metadata
        if extra_metadata:
            metadata.update(extra_metadata)

        return LLMResponse(text=text, metadata=metadata, raw=response)

    def _build_stream_response(self, chunk: dict[str, Any]) -> LLMResponse:
        """
        Build stream responses with consistent metadata from chunk payloads.

        Args:
            chunk (dict[str, Any]): The chunk payload from the Ollama model.

        Returns:
            LLMResponse: The constructed LLMResponse object containing text, metadata, and raw chunk.
        """
        return self._build_llm_response(
            chunk,
            extra_metadata={"done": chunk.get("done")},
        )


__all__ = ["OllamaLLMProvider"]
