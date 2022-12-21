import os
import hashlib
from pathlib import Path
from copy import deepcopy
from functools import partial
from typing import Union, Iterable

import spacy
import srsly
import torch
from tqdm.auto import tqdm

from aymurai.logging import get_logger
from aymurai.meta.types import DataItem, DataBlock
from aymurai.devtools.paths import resolve_package_path
from aymurai.meta.pipeline_interfaces import TrainModule
from aymurai.spacy.utils import format_entity, dataset_to_docbin

logger = get_logger(__name__)


class SpacyModel(TrainModule):
    CACHE_PATH = "/resources/cache/spacy"
    BASE_PATH = resolve_package_path("aymurai.spacy.models.configs")

    def __init__(
        self,
        base_config: Union[str, Path] = "",
        pretraining: bool = True,
        device: str = "gpu",
        dataset_cache: bool = True,
        batch_size: int = 64,
        entity_context_length: int = 10,
        categories: list[str] = [],
        categorizer_pipe: str = "",
        load_ents_as_spans: bool = False,
    ):
        # validations
        assert base_config, "base_config must be set."

        # TODO: handle device correctly
        self._device = device

        # cache
        self.dataset_cache = dataset_cache

        # categories for doc-categorizer
        self.categories = categories
        self.categorizer_pipe = categorizer_pipe

        # use spancat instead of ner
        self.load_ents_as_spans = load_ents_as_spans

        # set context length on entity export
        self.entity_context_length = entity_context_length

        # load nlp model
        global __nlp
        if (  # read config
            Path(base_config).is_file()
            or Path(f"{self.BASE_PATH}/{base_config}.cfg").is_file()
        ):
            if Path(f"{self.BASE_PATH}/{base_config}.cfg").is_file():
                base_config = f"{self.BASE_PATH}/{base_config}.cfg"

            base_config = spacy.util.ensure_path(base_config)
            config_path = self.get_config_path_from_disk(
                base_config,
                pretraining=pretraining,
            )
            config = spacy.util.load_config(config_path)
            __nlp = spacy.util.load_model_from_config(
                config,
                auto_fill=True,
                validate=True,
            )
            logger.info(f"loaded pipes: {__nlp.pipe_names}")

            if self.categories and self.categorizer_pipe:
                # add categories
                for cat in self.categories:
                    __nlp.get_pipe(categorizer_pipe).add_label(cat)
                logger.info(
                    f"loading categories: {__nlp.get_pipe(categorizer_pipe).labels}"
                )
            elif any([self.categories, self.categorizer_pipe]):
                logger.error("you must set categorizer_pipe and categories")
                raise ValueError("you must set categorizer_pipe and categories")
            else:  # no categorizer, no categories
                logger.warn("no categorizer, skiping")

            __nlp.initialize()
        else:  # load model using spacy api directly
            model = base_config
            __nlp = spacy.load(model)

        self.nlp = __nlp
        logger.info("model loaded.")

        self.config["nlp"]["batch_size"] = batch_size

    def get_config_path_from_disk(
        self,
        config_path: str,
        pretraining: bool = True,
    ):
        config_path = spacy.util.ensure_path(config_path)
        logger.info(f"loading base config ({config_path})")

        with open(config_path, "r") as file:
            data = {"base": file.read(), "pretraininig": pretraining}
            json = srsly.json_dumps(data, sort_keys=True)
            __base_config_hash = hashlib.md5(json.encode("utf-8")).hexdigest()

        # setup config
        new_config_path = Path(f"{self.CACHE_PATH}/{__base_config_hash}/config.cfg")
        spacy.cli.fill_config(
            base_path=config_path,
            output_file=new_config_path,
            pretraining=pretraining,
        )
        return new_config_path

    @property
    def pretraining(self):
        return bool(self.config["pretraining"])

    @property
    def config(self):
        return self.nlp.config

    @property
    def config_hash(self):
        json = srsly.json_dumps(self.config, sort_keys=True)
        return hashlib.md5(json.encode("utf-8"))

    def save(self, path: str):
        logger.info(f"saving component on {path}")
        __nlp.to_disk(path)

    @classmethod
    def load(cls, path: str):
        logger.info(f"loading component on {path}")
        return cls(base_config=path)

    def fit(self, train: DataBlock, val: DataBlock):
        logger.info("building train docbin")
        train_path = dataset_to_docbin(
            self.nlp,
            train,
            use_cache=self.dataset_cache,
            categories=self.categories,
            load_ents_as_spans=self.load_ents_as_spans,
        )
        logger.info("building val docbin")
        val_path = dataset_to_docbin(
            self.nlp,
            val,
            use_cache=self.dataset_cache,
            categories=self.categories,
            load_ents_as_spans=self.load_ents_as_spans,
        )

        # config cache path
        config_path = f"{self.CACHE_PATH}/{self.config_hash}/config.cfg"
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        self.config.to_disk(config_path)

        # model cache path
        json = {"train": train_path, "val": val_path, "config": config_path}
        model_hash = hashlib.md5(
            srsly.json_dumps(json, sort_keys=True).encode("utf-8")
        ).hexdigest()
        model_path = f"{self.CACHE_PATH}/model/{model_hash}"

        spacy.cli.train.train(
            config_path=config_path,
            output_path=model_path,
            overrides={
                "paths.train": train_path,
                "paths.dev": val_path,
            },
            use_gpu=0 if self._device == "gpu" else -1,
        )
        # load model back to pipeline
        logger.info("restoring model")
        torch.cuda.empty_cache()
        self.nlp = spacy.load(f"{model_path}/model-best")

    def format_items(self, docs: Iterable[spacy.tokens.Doc]):
        _format_entity = partial(format_entity, offset=self.entity_context_length)
        for doc in docs:
            ents = [_format_entity(ent) for ent in doc.ents]
            cats = doc.cats

            yield ents, cats

    def update_single(self, item: DataItem, pred) -> DataItem:
        if not pred:
            return item

        item = deepcopy(item)
        ents, cats = pred
        # add prediction as new field
        item["prediction"] = {}

        item["prediction"]["entities"] = list(ents)
        item["prediction"]["doc-cats"] = cats
        return item

    def predict(self, data: DataBlock) -> DataBlock:
        data = [self.predict_single(item) for item in data]

        return data
        # data = deepcopy(data)

        # texts = map(lambda x: x["data"]["doc.text"], data)
        # docs = self.nlp.pipe(texts)

        # predictions = self.format_items(docs)
        # for item, pred in tqdm(zip(data, predictions), total=len(data)):
        #     self.update_single(item, pred)

        # return data

    def predict_single(self, item: DataItem) -> DataItem:
        item = deepcopy(item)
        doc = self.nlp(item["data"]["doc.text"])
        pred = self.format_items([doc])

        item = self.update_single(item, next(pred))

        return item
