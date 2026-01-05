from __future__ import annotations

import os
from copy import deepcopy

import regex
import torch

from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import DocLabel, EntityAttributes
from aymurai.meta.pipeline_interfaces import TrainModule
from aymurai.meta.types import DataBlock, DataItem
from aymurai.models.decision.embeddingbag import (
    TinyEmbeddingBagClassifier,
    encode_text,
    make_offsets,
)
from aymurai.utils.download import download
from aymurai.utils.misc import get_element, is_url

logger = get_logger(__name__)


class DecisionEmbeddingBagBinRegex(TrainModule):
    def __init__(
        self,
        model_checkpoint: str,
        device: str = "cpu",
        threshold: float = 0.88,
        return_only_with_detalle: bool = True,
    ):
        self._device = device
        self._model_path = model_checkpoint
        self.threshold = threshold
        self.return_only_with_detalle = return_only_with_detalle

        basepath = os.getenv("AYMURAI_CACHE_BASEPATH", "/resources/cache/aymurai")
        if is_url(url := self._model_path):
            # Determine file extension from URL or default to safetensors
            if url.endswith(".pt"):
                ext = ".pt"
            else:
                ext = ".safetensors"
            output = f"{basepath}/{self.__class__.__name__}/model{ext}"
            logger.info(f"downloading model on {output}")
            os.makedirs(os.path.dirname(output), exist_ok=True)
            self._model_path = download(url, output=output)
            # If downloading safetensors, also try to download config
            if ext == ".safetensors":
                config_url = url.rsplit(".safetensors", 1)[0] + ".json"
                config_output = output.rsplit(".safetensors", 1)[0] + ".json"
                try:
                    download(config_url, output=config_output)
                except Exception as e:
                    logger.warning(f"Could not download config file: {e}")

        self.model, self.cfg = TinyEmbeddingBagClassifier.from_checkpoint(
            self._model_path,
            device=self._device,
        )
        self.model = self.model.eval()

    def fit(self, train: DataBlock, val: DataBlock) -> None:
        """
        Fit the model on training data. Currently not implemented.

        Args:
            train (DataBlock): Training data block.
            val (DataBlock): Validation data block.
        """
        logger.warning("fit routine not implemented")
        pass

    def predict(self, data: DataBlock) -> DataBlock:
        """
        Predict on a data block.

        Args:
            data (DataBlock): Input data block.

        Returns:
            DataBlock: Predicted data block.
        """
        # FIXME: optimize
        logger.warning("predict not optimized")
        return [self.predict_single(item) for item in data]

    def model_input_from_text(self, text: str) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Convert text to model input tensors.

        Args:
            text (str): Input text.

        Returns:
            tuple[torch.Tensor, torch.Tensor]: (flat_tokens, offsets) for model input.
        """
        token_ids = encode_text(text, self.cfg).to(self._device)
        return make_offsets([token_ids])

    def get_subcategory(self, text: str) -> list[str]:
        """
        Determine the subcategory of a decision based on its text.

        Args:
            text (str): Text of the decision.

        Returns:
            list[str]: List of subcategories for the decision.
        """
        pattern_no_hace_lugar = regex.compile(
            r"(?i)(no hacer? lugar|rechaz[ao]r?|no admitir|no convalidar|no autorizar|declarar inadmisible)"
        )
        match = pattern_no_hace_lugar.findall(text)
        if match:
            return ["no_hace_lugar"]
        else:
            return ["hace_lugar"]

    def gen_aymurai_entity(self, text: str, score: float) -> dict:
        """
        Generate an Aymurai entity dictionary for a decision.

        Args:
            text (str): Text of the decision.
            score (float): Confidence score of the decision.

        Returns:
            dict: Aymurai entity dictionary.
        """
        subcategory = self.get_subcategory(text)

        attrs = EntityAttributes(
            aymurai_label="DECISION",
            aymurai_label_subclass=subcategory,
            aymurai_method=self.__name__,
            aymurai_score=score,
        )

        ent = DocLabel(
            text=text,
            start_char=0,
            end_char=len(text),
            attrs=attrs,
        )
        ent = ent.model_dump()
        ent["label"] = "DECISION"
        ent["context_pre"] = ""
        ent["context_post"] = ""

        return ent

    def predict_single(self, item: DataItem) -> DataItem:
        """
        Predict a single data item.

        Args:
            item (DataItem): The data item to predict.

        Returns:
            DataItem: The predicted data item with added entities if applicable.
        """
        item = deepcopy(item)

        text = item["data"]["doc.text"]
        flat_tokens, offsets = self.model_input_from_text(text)
        with torch.no_grad():
            logits = self.model(flat_tokens, offsets)
            probs = logits.softmax(dim=1).cpu()
        prob = float(probs[0, 1])

        category = int(prob > self.threshold)
        score = prob

        if category == 0:  # not a decision
            return item

        ents = get_element(item, ["predictions", "entities"]) or []
        detalles = [ent for ent in ents if ent["label"] == "DETALLE"]
        if self.return_only_with_detalle and not detalles:
            return item

        ent = self.gen_aymurai_entity(text=text, category=category, score=score)
        ents.append(ent)

        if "predictions" not in item:
            item["predictions"] = {}

        item["predictions"]["entities"] = ents

        return item

    def save(self, basepath: str) -> dict:
        """
        Save the model to a directory.

        Args:
            basepath (str): Directory path to save the model.

        Returns:
            dict: A dictionary containing metadata about the saved model.
        """
        os.makedirs(basepath, exist_ok=True)

        # Use safetensors as the main format
        new_model_path = f"{basepath}/model.safetensors"
        self.model.save_checkpoint(new_model_path, use_safetensors=True)
        self._model_path = new_model_path
        logger.info(f"model saved on: {self._model_path}")

        return {
            "model_checkpoint": self._model_path,
            "device": self._device,
            "threshold": self.threshold,
            "return_only_with_detalle": self.return_only_with_detalle,
        }

    @classmethod
    def load(cls, path: str, **kwargs) -> DecisionEmbeddingBagBinRegex:
        """
        Load a DecisionEmbeddingBagBinRegex model from a directory.

        Args:
            path (str): Path to the directory containing the model files.

        Returns:
            DecisionEmbeddingBagBinRegex: The loaded model instance.
        """
        # Try safetensors first, then .pt
        safetensors_path = f"{path}/model.safetensors"
        pt_path = f"{path}/model.pt"

        if os.path.exists(safetensors_path):
            model_checkpoint = safetensors_path
        elif os.path.exists(pt_path):
            model_checkpoint = pt_path
        else:
            # Fallback to .pt for backward compatibility
            model_checkpoint = pt_path

        return cls(model_checkpoint=model_checkpoint, **kwargs)
