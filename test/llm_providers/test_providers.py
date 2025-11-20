import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aymurai.llm_providers import LLMProvider, LLMResponse, OllamaLLMProvider


class DummyProvider(LLMProvider):
    def __init__(self, **kwargs):
        super().__init__(model="dummy", **kwargs)
        self.last_prompt = None

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        self.last_prompt = prompt
        return LLMResponse(text=f"echo::{prompt}")

    def stream(self, prompt, **kwargs):
        return super().stream(prompt, **kwargs)


class FakeTokenizer:
    def encode(self, text, add_special_tokens: bool = False):
        return text.split()


class BaseProviderTests(unittest.TestCase):
    def test_chunk_text_respects_token_limit(self):
        provider = DummyProvider(max_context_tokens=4, chunk_overlap=1)
        text = "uno dos tres cuatro cinco seis"
        chunks = provider.chunk_text(text)
        self.assertGreater(len(chunks), 1)
        for i, chunk in enumerate(chunks):
            self.assertEqual(chunk.index, i)
            self.assertLessEqual(chunk.token_count, 4)

    def test_chunk_text_overlap_applied(self):
        provider = DummyProvider(max_context_tokens=3, chunk_overlap=1)
        text = "one two three four"
        chunks = provider.chunk_text(text)
        self.assertEqual([c.index for c in chunks], [0, 1])
        self.assertTrue(chunks[0].text.split()[-1] in chunks[1].text.split())

    def test_chunk_text_fallback_count(self):
        provider = DummyProvider(max_context_tokens=1)
        provider._tokenizer = type("EmptyTok", (), {"encode": lambda self, t: []})()
        chunks = provider.chunk_text("hello")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].token_count, 0)


class OllamaProviderTests(unittest.TestCase):
    def test_generate_builds_messages(self):
        provider = OllamaLLMProvider(model="llama3", system_prompt="Sistema")
        fake_response = {"message": {"content": "respuesta"}, "eval_count": 10}
        with patch("aymurai.llm_providers.ollama_provider.ollama.chat") as mock_chat:
            mock_chat.return_value = fake_response
            response = provider.generate("Hola")

        self.assertEqual(response.text, "respuesta")
        args, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["model"], "llama3")
        self.assertEqual(kwargs["messages"][0]["role"], "system")
        self.assertEqual(response.metadata.get("model"), "llama3")
        self.assertEqual(response.metadata.get("provider"), "ollama")
        self.assertIn("eval_count", response.metadata)
        self.assertIn("eval_duration", response.metadata)

    def test_generate_forwards_keep_alive(self):
        provider = OllamaLLMProvider(model="llama3", keep_alive=30)
        fake_response = {"message": {"content": "ok"}}
        with patch("aymurai.llm_providers.ollama_provider.ollama.chat") as mock_chat:
            mock_chat.return_value = fake_response
            _ = provider.generate("Hola")
        _, kwargs = mock_chat.call_args
        self.assertEqual(kwargs["keep_alive"], 30)

    def test_stream_yields_chunks(self):
        provider = OllamaLLMProvider(model="llama3")
        fake_chunks = iter(
            [
                {"message": {"content": "Hola"}, "done": False},
                {"message": {"content": " Mundo"}, "done": True},
            ]
        )
        with patch("aymurai.llm_providers.ollama_provider.ollama.chat") as mock_chat:
            mock_chat.return_value = fake_chunks
            pieces = list(provider.stream("Hola"))

        self.assertEqual([piece.text for piece in pieces], ["Hola", " Mundo"])
        _, kwargs = mock_chat.call_args
        self.assertTrue(kwargs["stream"])
        self.assertEqual(pieces[-1].text, " Mundo")
        self.assertTrue(pieces[-1].metadata.get("done"))

    def test_generate_raises_without_prompt_or_messages(self):
        provider = OllamaLLMProvider(model="llama3")
        with self.assertRaises(ValueError):
            provider.generate(prompt=None, messages=None)


class AsyncOllamaProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_generate_builds_messages(self):
        provider = OllamaLLMProvider(model="llama3", system_prompt="Sistema")
        fake_response = {"message": {"content": "respuesta"}, "eval_count": 10}
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value=fake_response)

        with patch(
            "aymurai.llm_providers.ollama_provider.AsyncClient",
            return_value=mock_client,
        ):
            response = await provider.async_generate("Hola")

        self.assertEqual(response.text, "respuesta")
        mock_client.chat.assert_awaited_once()
        _, kwargs = mock_client.chat.call_args
        self.assertEqual(kwargs["model"], "llama3")
        self.assertEqual(kwargs["messages"][0]["role"], "system")
        self.assertEqual(response.metadata.get("model"), "llama3")
        self.assertEqual(response.metadata.get("provider"), "ollama")
        self.assertIn("eval_count", response.metadata)

    async def test_async_stream_yields_chunks(self):
        provider = OllamaLLMProvider(model="llama3")

        async def fake_gen():
            yield {"message": {"content": "Hola"}, "done": False}
            yield {"message": {"content": " Mundo"}, "done": True}

        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value=fake_gen())

        with patch(
            "aymurai.llm_providers.ollama_provider.AsyncClient",
            return_value=mock_client,
        ):
            pieces = []
            last_chunk = None
            async for chunk in provider.async_stream("Hola"):
                pieces.append(chunk.text)
                last_chunk = chunk

        self.assertEqual(pieces, ["Hola", " Mundo"])
        mock_client.chat.assert_awaited()
        self.assertTrue(last_chunk.metadata.get("done"))


if __name__ == "__main__":
    unittest.main()
