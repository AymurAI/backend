import torch
from unidecode import unidecode

from aymurai.text.tokenizers.spanish import SpanishTokenizer


class Tokenizer(object):
    def __init__(self, vocab):
        self.max_len = 128
        self.tokenizer = SpanishTokenizer()
        self.vocab = vocab

    def save(self, path: str):
        torch.save(self.vocab, path)

    @classmethod
    def load(cls, path: str):
        vocab = torch.load(path)
        return cls(vocab=vocab)

    def __call__(self, text: str):
        text = text.lower()
        text = unidecode(text)
        return self.tokenizer(text)

    def encode(self, text: int):
        tokens = self(text)[: self.max_len]
        indices = self.vocab(tokens)
        indices = torch.tensor(indices, dtype=torch.int64)
        indices = torch.nn.functional.pad(indices, (0, self.max_len - len(indices)))
        return indices

    def encode_batch(self, texts):
        indices = [self.encode(text) for text in texts]
        indices = torch.stack(indices)
        return indices
