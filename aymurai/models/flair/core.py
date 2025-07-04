import os
import re
import logging
from copy import deepcopy

import flair
import numpy as np
from flair.data import Sentence
from more_itertools import collapse
from flair.models import SequenceTagger

from aymurai.logger import get_logger
from aymurai.utils.misc import is_url
from aymurai.utils.download import download
from aymurai.meta.types import DataItem, DataBlock
from aymurai.meta.pipeline_interfaces import TrainModule
from aymurai.meta.entities import Entity, EntityAttributes

flair.logger.setLevel(logging.ERROR)

logger = get_logger(__name__)


class FlairModel(TrainModule):
    def __init__(
        self,
        basepath: str,
        split_doc: bool = False,
        device: str = "cpu",
        use_tokenizer: bool = False,
    ):
        """
        Flair NER model module

        Args:
            basepath (str): parent directory to load model
            split_doc (bool, optional): split document on sentences. Defaults to False.
            device (str, optional): device where load model. Defaults to "cpu".
            use_tokenizer(bool, optional): whether to use custom tokenizer. Defaults to False.
        """  # noqa
        self.basepath = basepath
        self.split_doc = split_doc
        self.device = device
        self.use_tokenizer = use_tokenizer
        self.offset = 10

        # load model
        if is_url(url := basepath):
            basepath = os.getenv("AYMURAI_CACHE_BASEPATH", "/resources/cache/aymurai")
            model_path = f"{basepath}/{self.__name__}/model.pt"
            logger.info(f"downloading model on {model_path}")
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            self._model_path = download(url, output=model_path)
        else:
            model_path = basepath
        logger.info(f"loading model from {model_path}")
        self.model = SequenceTagger.load(model_path)

    @property
    def device(self):
        return flair.device

    @device.setter
    def device(self, value):
        logger.warning(f"setting flair device to `{value}` globaly")
        flair.device = value

    def save(self, path: str):
        self.basepath = path
        os.makedirs(path, exist_ok=True)

        filename = f"{path}/model.pt"

        logger.info(f"saving model on {filename}")
        self.model.save(filename)
        return {"basepath": self.basepath, "device": self.device}

    @classmethod
    def load(cls, path: str, **kwargs):
        return cls(basepath=path, **kwargs)

    def fit(self, train: DataBlock, val: DataBlock):
        return

    def predict(self, data: DataBlock) -> DataBlock:
        logger.info("flair batch prediction")
        # data = [self.predict_single(item) for item in data]

        # return data
        data = deepcopy(data)

        docs = [item["data"]["doc.text"] for item in data]

        sentences = [Sentence(sent, use_tokenizer=self.use_tokenizer) for sent in docs]

        self.model.predict(sentences)
        sentences = [sentence.get_spans("ner") for sentence in sentences]

        ents = map(self.format_entities, sentences)
        ents = list(ents)

        data = [self.set_ents(item, ents_) for item, ents_ in zip(data, ents)]

        return data

    def set_ents(self, item: DataItem, ents: list[dict]) -> DataItem:
        item = deepcopy(item)
        if "predictions" not in item:
            item["predictions"] = {}

        # overwrite predictions entities
        item["predictions"]["entities"] = list(ents)
        return item

    def format_entity(self, sentence: Sentence) -> dict:
        """
        format single flair entity to aymurai format

        Args:
            sentence (Sentence): document sentence

        Returns:
            dict: aymuray entity format
        """

        # pattern to match
        pattern = r"Span\[(\d+):(\d+)\]"

        label = sentence.get_label()
        text = label.data_point.text
        full_tokens = sentence.sentence.tokens

        label_value = label.value
        score = label.score

        start, end = re.findall(pattern, label.labeled_identifier)[0]
        start, end = int(start), int(end)

        start_char = label.data_point.start_position
        end_char = label.data_point.end_position

        # context surround
        last_token_idx = len(full_tokens)
        soffset = max(0, start - self.offset)
        eoffset = min(last_token_idx, end + self.offset)

        context_pre = " ".join([t.text for t in full_tokens[soffset:start]])
        context_post = " ".join([t.text for t in full_tokens[end:eoffset]])

        entity = Entity(
            start=start,
            end=end,
            label=label_value,
            text=text,
            start_char=start_char,
            end_char=end_char,
            context_pre=context_pre,
            context_post=context_post,
            attrs=EntityAttributes(
                aymurai_score=score,
                aymurai_method="ner/flair",
                aymurai_label=label_value,
            ),
        )
        return entity.model_dump()

    def format_entities(self, sentences: list[flair.data.Span]) -> list[dict]:
        """
        format list of entities to aymurai format

        Args:
            sentences (list[flair.data.Span]): list of flair spans

        Returns:
            list[dict]: aymurai format
        """

        # if not sentences return empty list
        if not sentences:
            return []

        return [self.format_entity(sentence) for sentence in sentences]

    def predict_single(self, item: DataItem) -> DataItem:
        item = deepcopy(item)

        doc = item["data"]["doc.text"]

        sentences = doc.splitlines() if self.split_doc else [doc]

        # number of tokens and characters per line
        n_tokens = [len(line.split()) for line in sentences]
        n_chars = [len(line) for line in sentences]

        sentences = [
            Sentence(
                sent,
                use_tokenizer=self.use_tokenizer,
            )
            for sent in sentences
        ]

        self.model.predict(sentences)
        sentences = [sentence.get_spans("ner") for sentence in sentences]

        ents = map(self.format_entities, sentences)
        ents = list(ents)

        # fix entities spans indices (start/end) to the original document
        accumulated_tokens = np.cumsum(n_tokens)
        for i, _ in enumerate(accumulated_tokens):
            if i == 0 or not ents[i]:
                continue

            for ent in ents[i]:
                ent["start"] += accumulated_tokens[i - 1] + i
                ent["end"] += accumulated_tokens[i - 1] + i

        accumulated_chars = np.cumsum(n_chars)
        for i, _ in enumerate(accumulated_chars):
            if i == 0 or not ents[i]:
                continue

            for ent in ents[i]:
                ent["start_char"] += accumulated_chars[i - 1] + i
                ent["end_char"] += accumulated_chars[i - 1] + i

        # filter empty entities
        ents = filter(bool, ents)
        ents = collapse(ents, base_type=dict)

        if "predictions" not in item:
            item["predictions"] = {}

        # overwrite predictions entities
        item["predictions"]["entities"] = list(ents)

        return item
