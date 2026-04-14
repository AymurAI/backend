from __future__ import annotations

from pathlib import Path

import flair
import torch
from flair.data import Corpus
from flair.embeddings import (
    FlairEmbeddings,
    StackedEmbeddings,
    TransformerWordEmbeddings,
)
from flair.models import SequenceTagger
from flair.trainers import ModelTrainer
from torch.optim.lr_scheduler import OneCycleLR

from aymurai.experiments.ner_flair_finetuning.config import (
    FlairModelConfig,
    TrainingConfig,
)
from aymurai.logger import get_logger

logger = get_logger(__name__)


def _fine_tune_with_compat(trainer: ModelTrainer, kwargs: dict) -> None:
    attempts = [
        [],
        ["scheduler"],
        ["scheduler", "save_model_each_k_epochs"],
        [
            "scheduler",
            "save_model_each_k_epochs",
            "anneal_factor",
            "patience",
            "min_learning_rate",
        ],
    ]
    last_error: TypeError | None = None
    for drop_keys in attempts:
        run_kwargs = dict(kwargs)
        for key in drop_keys:
            run_kwargs.pop(key, None)
        try:
            trainer.fine_tune(**run_kwargs)
            return
        except TypeError as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error


def _resolve_training_device(requested: str) -> torch.device:
    req = str(requested).strip().lower()

    def _mps_available() -> bool:
        return bool(
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        )

    if req in {"", "auto"}:
        if torch.cuda.is_available():
            logger.info("Using CUDA device (auto).")
            return torch.device("cuda")
        if _mps_available():
            logger.info("Using MPS device (auto).")
            return torch.device("mps")
        logger.info("Using CPU device (auto).")
        return torch.device("cpu")

    if req.startswith("cuda"):
        if torch.cuda.is_available():
            try:
                dev = torch.device(req)
                logger.info("Using requested CUDA device: %s", dev)
                return dev
            except Exception:
                logger.warning(
                    "Invalid CUDA device '%s'. Falling back to CUDA default.", req
                )
                return torch.device("cuda")
        logger.warning(
            "CUDA requested ('%s') but not available. Falling back to CPU.", req
        )
        return torch.device("cpu")

    if req == "mps":
        if _mps_available():
            logger.info("Using requested MPS device.")
            return torch.device("mps")
        logger.warning("MPS requested but not available. Falling back to CPU.")
        return torch.device("cpu")

    if req == "cpu":
        return torch.device("cpu")

    logger.warning("Unknown device '%s'. Falling back to auto selection.", req)
    return _resolve_training_device("auto")


def build_stacked_tagger(corpus: Corpus, config: FlairModelConfig) -> SequenceTagger:
    if config.finetune_from:
        return SequenceTagger.load(config.finetune_from)

    embeddings = StackedEmbeddings(
        [
            TransformerWordEmbeddings(
                config.model_id,
                layers=config.layers if hasattr(config, "layers") else "-1",
                subtoken_pooling=config.subtoken_pooling
                if hasattr(config, "subtoken_pooling")
                else "first",
                fine_tune=config.fine_tune,
                use_context=config.use_context,
                allow_long_sentences=config.allow_long_sentences,
            ),
            FlairEmbeddings(config.flair_forward),
            FlairEmbeddings(config.flair_backward),
        ]
    )

    tag_dictionary = corpus.make_label_dictionary(label_type="ner")
    return SequenceTagger(
        hidden_size=config.hidden_size,
        embeddings=embeddings,
        tag_dictionary=tag_dictionary,
        tag_type="ner",
        use_crf=config.use_crf,
        use_rnn=config.use_rnn,
        reproject_embeddings=config.reproject_embeddings,
        dropout=config.dropout if hasattr(config, "dropout") else 0.0,
    )


def execute_training(
    tagger: SequenceTagger,
    corpus: Corpus,
    config: TrainingConfig,
    output_path: Path,
) -> None:
    try:
        flair.device = _resolve_training_device(config.device)
    except Exception:
        logger.warning(
            "Could not initialize requested device '%s'; falling back to CPU.",
            config.device,
        )
        flair.device = torch.device("cpu")
    trainer = ModelTrainer(tagger, corpus)

    kwargs = {
        "base_path": str(output_path),
        "learning_rate": config.learning_rate,
        "mini_batch_size": config.mini_batch_size,
        "mini_batch_chunk_size": config.mini_batch_chunk_size,
        "max_epochs": config.max_epochs,
        "embeddings_storage_mode": config.embeddings_storage_mode,
        "weight_decay": config.weight_decay,
        "anneal_factor": config.anneal_factor,
        "patience": config.patience,
        "min_learning_rate": config.min_learning_rate,
        "use_final_model_for_eval": False,
        "scheduler": OneCycleLR,
        "save_model_each_k_epochs": max(1, int(config.save_model_each_k_epochs)),
    }

    try:
        _fine_tune_with_compat(trainer, kwargs)
    except RuntimeError as exc:
        msg = str(exc)
        mps_placeholder_error = (
            "Placeholder storage has not been allocated on MPS device"
        )
        if flair.device.type == "mps" and mps_placeholder_error in msg:
            logger.warning(
                "MPS runtime error detected (%s). Retrying training on CPU.",
                mps_placeholder_error,
            )
            try:
                if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                    torch.mps.empty_cache()
            except Exception:
                pass

            flair.device = torch.device("cpu")
            tagger.to(flair.device)
            trainer = ModelTrainer(tagger, corpus)
            _fine_tune_with_compat(trainer, kwargs)
        else:
            raise
