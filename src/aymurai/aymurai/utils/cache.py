import os
import json
import pickle
from typing import Any, Optional

import joblib
import diskcache

from aymurai.logging import get_logger
from aymurai.meta.types import DataItem
from aymurai.utils.json_encoding import EnhancedJSONEncoder

logger = get_logger(__name__)

DISKCACHE_ROOT = os.getenv("DISKCACHE_ROOT", "/resources/cache/diskcache")
cache = diskcache.Cache(DISKCACHE_ROOT)


def flatten_dict(current: dict, key: str = "", result: dict = {}) -> dict:
    """
    Flatten a dict

    Args:
        current (dict): dict to be flattened
        key (str, optional): key to be used. Defaults to "".
        result (dict, optional): result dict. Defaults to {}.

    Returns:
        dict: flattened dict
    """
    if type(current) is dict:
        for k in current:
            new_key = f"{key}.{k}" if len(key) > 0 else k
            flatten_dict(current[k], new_key, result)
    else:
        result[key] = current
    return result


def cache_clear(keys: list[str]):
    """
    Clear cache

    Args:
        keys (list[str]): keys to be cleared
    """
    for key in keys:
        cache.pop(key)


def get_cache_key(item: Any, context: Any = "") -> str:
    """
    Get cache key

    Args:
        item (Any): Data to hash
        context (Any): context object to create hash

    Returns:
        str: hash
    """

    if type(item) in [dict]:
        item = flatten_dict(item)
        item = sorted(tuple(item.items()))
        item = json.dumps(item, cls=EnhancedJSONEncoder)
    item_hash = joblib.hash(item)

    context_hash = joblib.hash(context)
    cache_key = f"context:{context_hash}-item:{item_hash}"

    return cache_key


def is_cached(key: str):
    return key in cache


def cache_save(
    data_item: DataItem,
    key: str,
):
    """
    save data on cache

    Args:
        data (Data): data to be cached
        key (str): key to store
    """

    data = pickle.dumps(data_item)

    logger.debug(f"saving cache to key: {key}")
    cache.set(key, data)


def cache_load(key: str) -> Optional[DataItem]:
    """
    load data from cache

    Args:
        key (str): key to load

    Returns:
        Optional[Data]: loaded data

    """

    if key in cache:
        # Retrieve the serialized object from cache
        data = cache.get(key)

        # Deserialize the object
        return pickle.loads(data)
