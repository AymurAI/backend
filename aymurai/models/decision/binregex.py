import os
import shutil
from copy import deepcopy

import regex
import torch
from unidecode import unidecode

from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import DocLabel, EntityAttributes
from aymurai.meta.pipeline_interfaces import TrainModule
from aymurai.meta.types import DataBlock, DataItem
from aymurai.models.decision.conv1d import Conv1dTextClassifier
from aymurai.models.decision.tokenizer import Tokenizer
from aymurai.utils.download import download
from aymurai.utils.misc import get_element, is_url

logger = get_logger(__name__)


class DecisionConv1dBinRegex(TrainModule):
    def __init__(
        self,
        tokenizer_path: str,
        model_checkpoint: str,
        device: str = "cpu",
        threshold: float = 0.88,
        return_only_with_detalle: bool = True,
    ):
        self._device = device
        self._tokenizer_path = tokenizer_path
        self._model_path = model_checkpoint
        self.threshold = threshold
        self.return_only_with_detalle = return_only_with_detalle

        # download if needed
        # tokenizer
        basepath = os.getenv("AYMURAI_CACHE_BASEPATH", "/resources/cache/aymurai")
        if is_url(url := self._tokenizer_path):
            output = f"{basepath}/{self.__name__}/tokenizer.pth"
            logger.info(f"downloading tokenizer on {output}")
            os.makedirs(os.path.dirname(output), exist_ok=True)
            self._tokenizer_path = download(url, output=output)
        # model
        if is_url(url := self._model_path):
            output = f"{basepath}/{self.__name__}/model.ckpt"
            logger.info(f"downloading model on {output}")
            os.makedirs(os.path.dirname(output), exist_ok=True)
            self._model_path = download(url, output=output)

        self.tokenizer = Tokenizer.load(self._tokenizer_path)
        self.model = Conv1dTextClassifier.load_from_checkpoint(
            self._model_path,
            map_location=self._device,
        )
        self.model = self.model.eval()

    def save(self, basepath: str) -> dict | None:
        # save tokenizer
        os.makedirs(basepath, exist_ok=True)
        self._tokenizer_path = f"{basepath}/tokenizer.pth"
        self.tokenizer.save(self._tokenizer_path)
        logger.info(f"tokenizer saved on: {self._tokenizer_path}")

        # save model
        new_model_path = f"{basepath}/model.ckpt"
        shutil.copy(self._model_path, new_model_path)
        self._model_path = new_model_path
        logger.info(f"model saved on: {self._model_path}")
        return {
            "tokenizer_path": self._tokenizer_path,
            "model_checkpoint": self._model_path,
            "device": self._device,
        }

    @classmethod
    def load(cls, path: str, **kwargs):
        return cls(
            tokenizer_path=f"{path}/tokenizer.pth",
            model_checkpoint=f"{path}/model.ckpt",
            **kwargs,
        )

    def fit(self, train: DataBlock, val: DataBlock):
        logger.warning("fit routine not implemented")
        pass

    def predict(self, data: DataBlock) -> DataBlock:
        # FIXME: optimize
        logger.warn("predict not optimized")
        return [self.predict_single(item) for item in data]

    def get_subcategory(self, text):
        pattern_no_hace_lugar = regex.compile(
            r"(?i)(no hacer? lugar|rechaz[ao]r?|no admitir|no convalidar|no autorizar|declarar inadmisible)"
        )
        match = pattern_no_hace_lugar.findall(text)
        if match:
            return ["no_hace_lugar"]
        else:
            return ["hace_lugar"]

    def gen_aymurai_entity(self, text: str, category: int, score: float):
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
        item = deepcopy(item)

        text = item["data"]["doc.text"]
        text = unidecode(text)
        input_ids = self.tokenizer.encode_batch([text]).to(self.model.device)
        with torch.no_grad():
            log_prob = self.model(input_ids).exp()
        # using category 1 as global score (binary)
        prob = log_prob.detach().numpy()[0, 1]

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
