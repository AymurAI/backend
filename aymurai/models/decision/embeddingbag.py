import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Tuple

import torch
from torch import nn
from unidecode import unidecode

try:
    from safetensors.torch import load_file as safe_load_file
    from safetensors.torch import save_file as safe_save_file
except Exception:  # pragma: no cover - optional dependency
    safe_load_file = None
    safe_save_file = None


def _normalize_text(text: str) -> str:
    text = unidecode(str(text)).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> list[str]:
    text = _normalize_text(text)
    return [tok for tok in text.split(" ") if tok]


def _hash_token(token: str, vocab_size: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "little") % vocab_size


@dataclass
class EmbeddingBagConfig:
    vocab_size: int = 20000
    embed_dim: int = 64
    max_tokens: int = 128
    dropout: float = 0.1
    num_classes: int = 2
    # allow passthrough of unknown config keys when loading from checkpoints
    extra: dict = field(default_factory=dict)


def _merge_config(ckpt_cfg: dict | None) -> EmbeddingBagConfig:
    """Merge checkpoint config with defaults, stashing unknown keys in extra."""
    ckpt_cfg = ckpt_cfg or {}
    cfg_defaults = EmbeddingBagConfig().__dict__
    merged = {**cfg_defaults}
    extra = {}
    for k, v in ckpt_cfg.items():
        if k in cfg_defaults:
            merged[k] = v
        else:
            extra[k] = v
    merged["extra"] = extra
    return EmbeddingBagConfig(**merged)


def encode_text(text: str, cfg: EmbeddingBagConfig) -> torch.Tensor:
    """Encode text into token ids using hashing; truncates to cfg.max_tokens."""
    tokens = _tokenize(text)
    token_ids = [_hash_token(tok, cfg.vocab_size) for tok in tokens[: cfg.max_tokens]]
    if not token_ids:
        token_ids = [0]
    return torch.tensor(token_ids, dtype=torch.long)


def make_offsets(token_seqs: list[torch.Tensor]) -> Tuple[torch.Tensor, torch.Tensor]:
    """Flatten variable-length token sequences for EmbeddingBag."""
    device = token_seqs[0].device if token_seqs else None
    offsets = torch.zeros(len(token_seqs), dtype=torch.long, device=device)
    flat = []
    total = 0
    for i, seq in enumerate(token_seqs):
        offsets[i] = total
        flat.append(seq)
        total += len(seq)
    flat_tokens = torch.cat(flat) if flat else torch.tensor([], device=device)
    return flat_tokens, offsets


class TinyEmbeddingBagClassifier(nn.Module):
    def __init__(self, cfg: EmbeddingBagConfig):
        super().__init__()
        self.cfg = cfg
        self.embedding = nn.EmbeddingBag(cfg.vocab_size, cfg.embed_dim, mode="mean")
        self.dropout = nn.Dropout(cfg.dropout)
        self.head = nn.Linear(cfg.embed_dim, cfg.num_classes)

    def forward(self, tokens: torch.Tensor, offsets: torch.Tensor) -> torch.Tensor:
        x = self.embedding(tokens, offsets)
        x = self.dropout(x)
        return self.head(x)

    @classmethod
    def from_checkpoint(
        cls, checkpoint_path: str, device: str = "cpu"
    ) -> tuple["TinyEmbeddingBagClassifier", EmbeddingBagConfig]:
        if checkpoint_path.endswith(".safetensors"):
            if safe_load_file is None:
                raise ImportError(
                    "safetensors is not installed; cannot load .safetensors checkpoint"
                )
            state = safe_load_file(checkpoint_path, device=device)
            cfg_path = os.path.splitext(checkpoint_path)[0] + ".json"
            cfg_data = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    cfg_data = json.load(f)
            cfg = _merge_config(cfg_data)
        else:
            checkpoint = torch.load(checkpoint_path, map_location=device)
            cfg = _merge_config(checkpoint.get("config", {}))
            state = checkpoint.get("state_dict", checkpoint)

        model = cls(cfg)
        model.load_state_dict(state)
        model.to(device)
        model.eval()
        return model, cfg

    def save_checkpoint(
        self,
        save_path: str,
        use_safetensors: bool = True,
    ) -> str:
        """Save model checkpoint.

        Args:
            save_path: Path to save checkpoint. Extension determines format.
                      If no extension, .safetensors or .pt will be added based on use_safetensors.
            use_safetensors: If True and no extension provided, save as .safetensors.
                           If False, save as .pt format.

        Returns:
            str: The actual path where the checkpoint was saved.
        """
        # Determine save format based on extension or flag
        if not save_path.endswith((".safetensors", ".pt")):
            ext = ".safetensors" if use_safetensors else ".pt"
            save_path = save_path + ext

        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)

        if save_path.endswith(".safetensors"):
            if safe_save_file is None:
                raise ImportError(
                    "safetensors is not installed; cannot save .safetensors checkpoint. "
                    "Install with: pip install safetensors"
                )
            # Save model weights as safetensors
            safe_save_file(self.state_dict(), save_path)
            # Save config as JSON
            cfg_path = os.path.splitext(save_path)[0] + ".json"
            with open(cfg_path, "w") as f:
                json.dump(
                    {
                        "vocab_size": self.cfg.vocab_size,
                        "embed_dim": self.cfg.embed_dim,
                        "max_tokens": self.cfg.max_tokens,
                        "dropout": self.cfg.dropout,
                        "num_classes": self.cfg.num_classes,
                        **self.cfg.extra,
                    },
                    f,
                    indent=2,
                )
        else:
            # Save as PyTorch checkpoint with config embedded
            torch.save(
                {
                    "state_dict": self.state_dict(),
                    "config": {
                        "vocab_size": self.cfg.vocab_size,
                        "embed_dim": self.cfg.embed_dim,
                        "max_tokens": self.cfg.max_tokens,
                        "dropout": self.cfg.dropout,
                        "num_classes": self.cfg.num_classes,
                        **self.cfg.extra,
                    },
                },
                save_path,
            )

        return save_path
