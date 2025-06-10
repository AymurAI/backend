from typing import Any, Optional

from typing_extensions import TypedDict


class Annotation(TypedDict):
    label: str
    value: Any


class DataItem(TypedDict):
    path: str
    extension: str
    dataset: str
    data: Optional[dict]
    annotations: Optional[list[Annotation]]
    predictions: Optional[list[Annotation]]


DataBlock = list[DataItem]
PredictionBlock = list[Annotation]
