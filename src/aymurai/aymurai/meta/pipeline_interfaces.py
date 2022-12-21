import abc
from typing import Optional

from aymurai.meta.types import DataItem, DataBlock


class Transform(metaclass=abc.ABCMeta):
    @property
    def __name__(self):
        return self.__class__.__name__

    @abc.abstractmethod
    def __call__(self, item: DataItem) -> DataItem:
        pass


class TrainModule(object):
    @property
    def __name__(self):
        return self.__class__.__name__

    @abc.abstractmethod
    def save(self, path: str) -> Optional[dict]:
        pass

    @abc.abstractmethod
    def load(self, path: str):
        pass

    @abc.abstractmethod
    def fit(self, train: DataBlock, val: DataBlock):
        pass

    @abc.abstractmethod
    def predict(self, data: DataBlock) -> DataBlock:
        pass

    def predict_single(self, item: DataItem) -> DataItem:
        pass
