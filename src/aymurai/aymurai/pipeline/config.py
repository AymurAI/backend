import json
import importlib
from typing import Any
from copy import deepcopy

import srsly

from aymurai.meta.config import ConfigSchema
from aymurai.meta.pipeline_interfaces import Transform, TrainModule


class PipeNotFoundError(Exception):
    """Pipe not valid or found"""

    pass


def resolve_obj(func_path: Any):
    """
    Resolve a string path to a callable object

    Args:
        func_path (str): String path to the callable object

    Returns:
        Callable: Callable object
    """
    if not isinstance(func_path, str):
        return func_path

    # else func is a string
    module_name = ".".join(func_path.split(".")[:-1])

    module = importlib.import_module(module_name)

    obj_name = func_path.split(".")[-1]
    obj = getattr(module, obj_name)
    return obj


def json2config(config: str) -> ConfigSchema:
    """
    Pipeline config validator. Check if it is a valid config object.
    Also transform JSON config format to the callable function format

    Args:
        config (str): Config as json

    Raises:
        ModuleNotFoundError: Pipe or model is not valid

    Returns:
        ConfigSchema: Config in functional format
    """
    config = json.loads(config)

    for pipeline in ["preprocess", "models", "postprocess"]:
        for i, pipe in enumerate(config[pipeline]):
            func_path, kwargs = pipe

            for key, value in kwargs.items():
                try:
                    func_ = resolve_obj(value)
                    if callable(func_):
                        kwargs[key] = func_
                # except ModuleNotFoundError:
                except Exception:
                    pass

            if callable(func_path):
                continue
            # # else func is a string
            # module_name = ".".join(func_path.split(".")[:-1])
            # # if func_path not in pipes_list():
            # # raise PipeNotFoundError(f"{func_path} not found in pipeline list")

            # # importlib.invalidate_caches()  # clear modules cache
            # module = importlib.import_module(module_name)

            # obj_name = func_path.split(".")[-1]
            # obj = getattr(module, obj_name)
            obj = resolve_obj(func_path)

            if pipeline == "models":
                assert issubclass(
                    obj, TrainModule
                ), f"{obj} is not a valid TrainModule object"
            else:
                assert issubclass(
                    obj, Transform
                ), f"{obj} is not a valid Transform object"

            config[pipeline][i] = (obj, kwargs)

    return config


def config2json(config: ConfigSchema) -> str:
    """
    Pipeline config validator. Check if it is a valid config object.
    Also transform "callable" config format to JSON format

    Args:
        config (ConfigSchema): Config object

    Raises:
        ModuleNotFoundError: Pipe or model is not valid

    Returns:
        ConfigSchema: Config in functional JSON
    """
    config = deepcopy(config)
    for pipeline in ["preprocess", "models", "postprocess"]:
        for i, pipe in enumerate(config[pipeline]):
            obj, kwargs = pipe
            # better be sure not to anything of the original object
            kwargs = deepcopy(kwargs)
            path = f"{obj.__module__}.{obj.__name__}"
            for key, value in kwargs.items():
                if callable(value):
                    kwargs[key] = f"{value.__module__}.{value.__name__}"

            config[pipeline][i] = (path, kwargs)

    return json.dumps(config, indent=4)


def config2yaml(config: ConfigSchema) -> str:
    """
    Pipeline config validator. Check if it is a valid config object.
    Also transform "callable" config format to YAML format

    Args:
        config (ConfigSchema): Config object

    Raises:
        ModuleNotFoundError: Pipe or model is not valid

    Returns:
        ConfigSchema: Config in functional YAML
    """
    cfg = config2json(config)
    cfg = srsly.json_loads(cfg)
    return srsly.yaml_dumps(cfg)
