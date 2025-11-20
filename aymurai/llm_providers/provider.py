from __future__ import annotations

import abc
from typing import Any, Sequence

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """Standard response wrapper for any LLM provider."""

    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw: Any | None = None


class DocumentChunk(BaseModel):
    """Represents a chunked portion of a larger document."""

    text: str
    token_count: int
    index: int


TokenizerType = Any


class LLMProvider(abc.ABC):
    """Base class with shared utilities for concrete LLM providers."""

    def __init__(
        self,
        model: str,
        *,
        tokenizer: TokenizerType | None = None,
        max_context_tokens: int | None = None,
        chunk_overlap: int = 0,
    ) -> None:
        self.model_name = model
        self._tokenizer = tokenizer
        self.max_context_tokens = max_context_tokens
        self.chunk_overlap = max(chunk_overlap, 0)

    @abc.abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """
        Generate a response from the model using the provided prompt.

        Args:
            prompt (str): The input prompt to generate a response for.
            **kwargs: Additional provider-specific parameters.

        Returns:
            LLMResponse: The generated response wrapped in an LLMResponse object.
        """
        pass

    @abc.abstractmethod
    def stream(self, prompt: str, **kwargs):
        """
        Stream the response from the model using the provided prompt.

        Args:
            prompt (str): The input prompt to generate a response for.
            **kwargs: Additional provider-specific parameters.

        Raises:
            NotImplementedError: If the provider does not support streaming.
        """
        raise NotImplementedError("This provider does not support streaming.")

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        Args:
            text (str): The input text to count tokens for.

        Returns:
            int: The number of tokens in the input text.
        """
        tokens = self._tokenize(text)
        return len(tokens)

    def chunk_text(
        self,
        text: str,
        *,
        max_tokens: int | None = None,
        overlap: int | None = None,
    ) -> list[DocumentChunk]:
        """
        Chunk text ensuring every piece respects the token budget.

        Args:
            text (str): The input text to chunk.
            max_tokens (int | None): Optional maximum tokens per chunk.
            overlap (int | None): Optional token overlap between chunks.

        Returns:
            list[DocumentChunk]: A list of document chunks.
        """
        cleaned_text = text.strip()
        if not cleaned_text:
            return []

        limit = max_tokens or self.max_context_tokens
        if limit is None:
            total_tokens = self.count_tokens(cleaned_text)
            return [DocumentChunk(text=cleaned_text, token_count=total_tokens, index=0)]

        words = cleaned_text.split()
        if not words:
            return []

        chunks = []
        overlap_tokens = overlap if overlap is not None else self.chunk_overlap
        current_words = []
        current_tokens = 0

        for word in words:
            if not current_words:
                current_words = [word]
                current_tokens = self.count_tokens(" ".join(current_words))
                if current_tokens > limit:
                    chunks.append(
                        DocumentChunk(
                            text=current_words[0],
                            token_count=current_tokens,
                            index=len(chunks),
                        )
                    )
                    current_words = []
                    current_tokens = 0
                continue

            tentative_words = current_words + [word]
            tentative_text = " ".join(tentative_words)
            tentative_tokens = self.count_tokens(tentative_text)

            if tentative_tokens <= limit:
                current_words = tentative_words
                current_tokens = tentative_tokens
                continue

            chunk_text = " ".join(current_words)
            chunks.append(
                DocumentChunk(
                    text=chunk_text, token_count=current_tokens, index=len(chunks)
                )
            )

            carry_over = self._overlap_tail(current_words, overlap_tokens)
            current_words = carry_over + [word]
            current_tokens = self.count_tokens(" ".join(current_words))

            if current_tokens > limit:
                chunk_text = " ".join(current_words)
                chunks.append(
                    DocumentChunk(
                        text=chunk_text, token_count=current_tokens, index=len(chunks)
                    )
                )
                current_words = []
                current_tokens = 0

        if current_words:
            chunk_text = " ".join(current_words)
            chunks.append(
                DocumentChunk(
                    text=chunk_text,
                    token_count=current_tokens or self.count_tokens(chunk_text),
                    index=len(chunks),
                )
            )

        return chunks

    def _tokenize(self, text: str) -> Sequence[Any]:
        """
        Tokenize text using the configured tokenizer or fallback to whitespace.

        Args:
            text (str): The input text to tokenize.

        Returns:
            Sequence[Any]: The sequence of tokens.
        """
        if self._tokenizer is None:
            return text.split()

        tokenizer = self._tokenizer
        if hasattr(tokenizer, "encode"):
            return tokenizer.encode(text)

        if callable(tokenizer):
            tokens = tokenizer(text)
            if isinstance(tokens, dict):
                return tokens.get("input_ids", [])
            return tokens

        return text.split()

    def _overlap_tail(self, words: list[str], overlap_tokens: int) -> list[str]:
        """
        Get the tail overlap of words based on the token budget.

        Args:
            words (list[str]): The list of words to consider for overlap.
            overlap_tokens (int): The token budget for the overlap. Must be non-negative.

        Returns:
            list[str]: The list of words representing the tail overlap.
        """
        assert overlap_tokens >= 0, "`overlap_tokens` must be non-negative."

        if not words or overlap_tokens == 0:
            return []

        tail = []

        for word in reversed(words):
            tail.insert(0, word)
            token_budget = self.count_tokens(" ".join(tail))
            if token_budget >= overlap_tokens:
                break

        return tail


__all__ = ["DocumentChunk", "LLMProvider", "LLMResponse"]
