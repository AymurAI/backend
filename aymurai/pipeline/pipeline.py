import os

from aymurai.logger import get_logger
from aymurai.meta.types import DataItem, DataBlock

from .training import TrainingPipeline
from .preprocess import PreProcessPipeline
from .postprocess import PostProcessPipeline
from .config import config2json, config2yaml, json2config

logger = get_logger(__name__)


class AymurAIPipeline(object):
    """
    AymurAIPipeline provides a set of separated pipelines in preprocessing,
        training and postprocessing.
    """

    def __init__(self, config: dict, print_config: bool = True):
        """

        Args:
            config (Dict): pipeline config, it must have the following keys:
                preprocess, models, postprocess.
            print_config (bool, optional): print config. Default True.
        """
        self.config = config

        self.logger = logger
        if log_level := config.get("log_level"):
            self.logger.setLevel(log_level.upper())
            self.logger.debug(f"Pipeline logger level: {log_level.upper()}")

        if print_config:
            self.logger.info("pipeline config:")
            self.logger.info(self)

        self.pre_process = PreProcessPipeline(config, logger=self.logger)
        self.training_pipeline = TrainingPipeline(config, logger=self.logger)
        self.post_process = PostProcessPipeline(config, logger=self.logger)

    def __repr__(self):
        return config2yaml(self.config)

    @property
    def models(self):
        return self.training_pipeline.models

    def preprocess(self, data: DataBlock):
        """
        Method to preprocess the data

        Args:
            data (DataBlock)
        """
        return self.pre_process.transform(data)

    def postprocess(self, data: DataBlock):
        """
        Method to postprocess the data

        Args:
            data (DataBlock)
        """
        return self.post_process.transform(data)

    def fit(self, train: DataBlock, val: DataBlock):
        """
        Method to train the pipeline.

        Args:
            data_train (DataBlock): training data.
        """
        self.training_pipeline.fit(train, val)

    def predict_single(self, item: DataItem) -> DataItem:
        """
        Method to generate predictions over one item.

        Args:
            config (Dict): pipeline config, it must have the following keys:
                           preprocess, models, postprocess.
            item (DataItem): data item

        Returns:
            item: DataItem with predictions.
        """
        item = self.training_pipeline.predict_single(item)

        return item

    def predict(self, data_test: DataBlock) -> DataBlock:
        """
        Method to generate predictions over test.

        Args:
            config (Dict): pipeline config, it must have the following keys:
                           preprocess, models, postprocess.
            data_test (DataBlock): test data

        Returns:
            DataBlock: data_test with predictions.
        """
        data_test = self.training_pipeline.predict(data_test)

        return data_test

    def save(self, path: str):
        """
        save pipeline

        Args:
            path (str): parent path where save pipeline
        """
        os.makedirs(path, exist_ok=True)

        # save & get config kwargs to be overwriten on pipeline save
        overwrite_config = self.training_pipeline.save(path)
        self.config.update(overwrite_config or {})

        # save config file
        json_config = config2json(self.config)
        logger.info(f"saving pipeline on: {os.path.join(path, 'pipeline.json')}")
        with open(os.path.join(path, "pipeline.json"), "w") as file:
            print(json_config, file=file)

    @classmethod
    def load(cls, path: str, print_config: bool = True):
        logger.info(f"loading pipeline from: {os.path.join(path, 'pipeline.json')}")

        with open(os.path.join(path, "pipeline.json"), "r") as file:
            json_config = file.read()
        config = json2config(json_config)
        obj = cls(config=config, print_config=print_config)
        # FIXME: test the correct way to load training pipeline

        return obj
