from collections import OrderedDict

from tqdm.auto import tqdm
from joblib import Parallel, delayed

from aymurai.logger import get_logger
from aymurai.meta.types import DataItem, DataBlock
from aymurai.meta.pipeline_interfaces import Transform
from aymurai.utils.cache import cache_load, cache_save, get_cache_key


class PreProcessPipeline(object):
    def __init__(self, config, logger=None):
        """
        Preprocessing pipeline

        Args:
            config (dict): Preprocessing config
            logger (logging.Logger, optional): Logger. Defaults to None.

            Raises:
                TypeError: If steps is not a subclass of Transform
        """
        self.config = config
        self.logger = logger or get_logger(__name__)

        self.raw_steps = self.config.get("preprocess")
        self.steps = []
        self.steps_repr = OrderedDict()

        for step in self.raw_steps:
            transform, kwargs = step

            if not issubclass(transform, Transform):
                raise TypeError(
                    f"steps must be a subclass of {type(Transform)}"
                    f", instead got {type(transform)}."
                )

            self.steps.append(transform(**kwargs))
            self.steps_repr[transform.__name__] = kwargs

        self.logger.debug(f"preprocessing config: {self.steps_repr}")

    def apply_transforms(self, data_item: DataItem) -> DataItem:
        """
        Apply preprocessing pipeline to a data item

        Args:
            data_item (DataItem): Data item to be processed

        Returns:
            DataItem: Processed data item
        """

        use_cache = self.config.get("use_cache")

        cache_key = get_cache_key(data_item, self.steps_repr)
        if use_cache and (cache_data := cache_load(key=cache_key, logger=self.logger)):
            return cache_data

        for transform in self.steps:
            data_item = transform(data_item)

        if use_cache:
            cache_save(data_item, key=cache_key, logger=self.logger)

        return data_item

    def transform(self, data_block: DataBlock) -> DataBlock:
        """
        Apply preprocessing pipeline to a data block

        Args:
            data_block (DataBlock): Data block to be processed

        Returns:
            DataBlock: Processed data block
        """

        self.logger.info("doing preprocessing tasks...")
        if "multiprocessing" in self.config.keys():
            njobs = self.config["multiprocessing"].get("njobs", -1)
            backend = self.config["multiprocessing"].get("backend", "multiprocessing")

            batch_size = self.config["multiprocessing"].get("batch_size", 1)

            parallel = Parallel(n_jobs=njobs, backend=backend, batch_size=batch_size)

            delayed_transforms = delayed(self.apply_transforms)
            data_block = parallel(
                delayed_transforms(x) for x in tqdm(data_block, desc="")
            )

            return data_block

        data_block = [self.apply_transforms(x) for x in tqdm(data_block, desc="")]

        return data_block
