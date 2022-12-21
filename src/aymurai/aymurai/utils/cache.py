import json
import pickle
from typing import Any, Optional

import joblib
from redis import Redis

from aymurai.logging import get_logger
from aymurai.meta.types import DataItem
from aymurai.utils.json_encoding import EnhancedJSONEncoder

redis = Redis()


def flatten_dict(current: dict, key: str = "", result: dict = {}) -> dict:
    if type(current) is dict:
        for k in current:
            new_key = f"{key}.{k}" if len(key) > 0 else k
            flatten_dict(current[k], new_key, result)
    else:
        result[key] = current
    return result


def cache_clear(keys: list[str]):
    redis.delete(*keys)


def get_cache_key(obj: Any, context: Any = "") -> str:
    """cache hasher

    Args:
        data (Data): Data to hash
        context: context object to create hash

    Returns:
        str: hash
    """

    item = obj
    if type(item) in [dict]:
        item = flatten_dict(obj)
        item = sorted(tuple(item.items()))
        item = json.dumps(item, cls=EnhancedJSONEncoder)
    item_hash = joblib.hash(item)

    context_hash = joblib.hash(context)
    cache_key = f"context:{context_hash}-item:{item_hash}"

    return cache_key


def cache_save(
    data_item: DataItem,
    key: str,
    logger=None,
):
    """save data on cache

    Args:
        data (Data): data to be cached
        key (str): key to store
        logger (optional): logger
    """
    logger = logger or get_logger(__name__)

    data_string = pickle.dumps(data_item)

    logger.debug(f"saving cache to key: {key}")
    redis.mset({key: data_string})


def cache_load(
    key: str,
    logger=None,
) -> Optional[DataItem]:
    """restore data from cached

    Args:
        key (str): key to retrive
        logger (optional): logger

    Returns:
        Data
    """
    logger = logger or get_logger(__name__)

    if redis.exists(key):
        logger.debug(f"founded cache key: {key}")
        loaded_data = redis.get(key)
        loaded_data = pickle.loads(loaded_data)
        return loaded_data
