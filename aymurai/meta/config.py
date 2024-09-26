from typing import Any, Union, Optional, TypedDict

from aymurai.meta.pipeline_interfaces import Transform, TrainModule

PipeSchema = tuple[Union[str, Transform], dict[str, Any]]
ModelSchema = tuple[Union[str, TrainModule], dict[str, Any]]


class ConfigSchema(TypedDict):
    preprocess: list[PipeSchema]
    models: list[ModelSchema]
    postprocess: list[PipeSchema]
    multiprocessing: Optional[dict]


EMPTY_CONFIG = ConfigSchema(preprocess=[], models=[], postprocess=[])
