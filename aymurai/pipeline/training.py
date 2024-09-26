from typing import Dict, Optional
from collections import OrderedDict

from aymurai.logging import get_logger
from aymurai.meta.types import DataItem, DataBlock
from aymurai.meta.pipeline_interfaces import TrainModule
from aymurai.utils.cache import cache_load, cache_save, get_cache_key

logger = get_logger(__name__)


class TrainingPipeline(object):
    def __init__(self, config: Dict, logger=None):
        """
        Training pipeline

        Args:
            config (Dict): Training pipeline config
            logger (Optional[logging.Logger], optional): Logger. Defaults to None.

            Raises:
                TypeError: If steps is not a subclass of TrainModule
        """

        self.config = config
        self.logger = logger or get_logger(__name__)

        self.raw_steps = self.config.get("models")
        self.models = []
        self.models_repr = OrderedDict()

        for step in self.raw_steps:
            model, kwargs = step

            if not issubclass(model, TrainModule):
                raise TypeError(
                    f"steps must be a subclass of {type(TrainModule)}"
                    f", instead got {type(model)}."
                )
            instance = model(**kwargs)
            self.models.append(instance)
            self.models_repr[model.__name__] = kwargs

        self.logger.debug(f"preprocessing config: {self.models_repr}")

    def fit(self, train: DataBlock, val: DataBlock):
        """
        For each model defined in config train
        the model and append it to self.models.

        Args:
            data (DataBlock): data to train
        """
        logger.info("doing traning tasks...")
        for model in self.models:
            model.fit(train, val)
            self.logger.info(f"training model {model.__name__} done")

    def predict_single(self, item: DataItem) -> DataItem:
        """For each model trained call model.predict
         and chain the output for the following model

        Args:
            item (DataItem): data to make predictions

        Returns:
            DataItem: predictions for item
        """

        # for each model call method predict with output from previous model.

        use_cache = self.config.get("use_cache")

        cache_key = get_cache_key(item, self.models_repr)
        if use_cache and (cache_data := cache_load(key=cache_key, logger=self.logger)):
            return cache_data

        for model in self.models:
            item = model.predict_single(item)

        if use_cache:
            cache_save(item, key=cache_key, logger=self.logger)

        return item

    def predict(self, data_block: DataBlock) -> DataBlock:
        """For each model trained call model.predict
         and chain the output for the following model

        Args:
            data (DataBlock): data to make predictions

        Returns:
            DataBlock: predictions
        """

        # for each model call method predict with output from previous model.

        use_cache = self.config.get("use_cache")

        cache_key = get_cache_key(data_block, self.models_repr)
        if use_cache and (cache_data := cache_load(key=cache_key, logger=self.logger)):
            return cache_data

        for model in self.models:
            data_block = model.predict(data_block)

        if use_cache:
            cache_save(data_block, key=cache_key, logger=self.logger)

        return data_block

    def save(self, path: str) -> Optional[dict]:
        """
        save models pipeline

        Args:
            path (str): parent path where store models

        Returns:
            overwrite_config: fields to be overwrite in saving
        """
        for i, model in enumerate(self.models):
            overwrite_config = model.save(f"{path}/{model.__name__}")
            self.config["models"][i][1].update(overwrite_config or {})
        return self.config

    def load(self, path: str):
        """
        load models pipeline

        Args:
            path (str): parent path where models are stored

        DEPRECATED: models loades in __init__ method
        """
        pass
