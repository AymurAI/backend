import unittest
from unittest.mock import patch

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


class FakePipeline:
    def __init__(self):
        self.calls = []
        self._tokenizer = FakeTokenizer()

    def __call__(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return [{"generated_text": f"generated::{prompt}"}]

    @property
    def tokenizer(self):
        return self._tokenizer


class BaseProviderTests(unittest.TestCase):
    def test_chunk_text_respects_token_limit(self):
        provider = DummyProvider(max_context_tokens=4, chunk_overlap=1)
        text = "uno dos tres cuatro cinco seis"
        chunks = provider.chunk_text(text)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(chunk.token_count, 4)


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


if __name__ == "__main__":
    unittest.main()
