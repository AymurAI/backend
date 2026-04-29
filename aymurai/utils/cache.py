import json
import os
import pickle
from typing import Any

import diskcache
import joblib

from aymurai.logger import get_logger
from aymurai.utils.json_encoding import EnhancedJSONEncoder

logger = get_logger(__name__)

DISKCACHE_ROOT = os.getenv("DISKCACHE_ROOT", "/resources/cache/diskcache")
cache = diskcache.Cache(DISKCACHE_ROOT)


def flatten_dict(current: dict, key: str = "", result: dict = {}) -> dict:
    """
    Flatten nested dictionaries into a dotted-key mapping.

    Args:
        current (dict): Source dictionary to flatten.
        key (str): Parent key prefix. Defaults to "".
        result (dict, optional): Accumulator reused across recursion. Defaults to {}.

    Returns:
        dict: Mapping of flattened keys to terminal values.
    """
    if type(current) is dict:
        for k in current:
            new_key = f"{key}.{k}" if len(key) > 0 else k
            flatten_dict(current[k], new_key, result)
    else:
        result[key] = current
    return result


def cache_clear(keys: list[str]) -> None:
    """
    Remove the provided keys from the disk-backed cache.

    Args:
        keys (list[str]): Cache keys to delete.
    """
    for key in keys:
        cache.pop(key)


def get_cache_key(item: Any, context: Any = "") -> str:
    """
    Build a stable cache key combining the item payload and context.

    Args:
        item (Any): Value to hash into the key namespace.
        context (Any): Additional context used to scope the key. Defaults to "".

    Returns:
        str: Deterministic hash suitable for cache lookups.
    """

    if type(item) in [dict]:
        item = flatten_dict(item)
        item = sorted(tuple(item.items()))
        try:
            item = json.dumps(item, cls=EnhancedJSONEncoder)
        except TypeError:
            # Last-resort safety: avoid crashing preprocessing if a value is still not
            # serializable under the custom encoder.
            item = json.dumps(item, default=str)
    item_hash = joblib.hash(item)

    context_hash = joblib.hash(context)
    cache_key = f"context:{context_hash}-item:{item_hash}"

    return cache_key


def is_cached(key: str) -> bool:
    """
    Determine whether a cache entry exists for the given key.

    Args:
        key (str): Cache key to inspect.

    Returns:
        bool: True when the key is present, otherwise False.
    """
    return key in cache


def cache_save(data_item: Any, key: str) -> None:
    """
    Persist a Python object in the disk-backed cache.

    Args:
        data_item (Any): Serializable payload to store.
        key (str): Cache key under which the payload is saved.

    Returns:
        None: This function does not return a value.
    """

    data = pickle.dumps(data_item)

    logger.debug(f"saving cache to key: {key}")
    cache.set(key, data)


def cache_load(key: str) -> Any | None:
    """
    Retrieve and deserialize a cached payload when present.

    Args:
        key (str): Cache key to resolve.

    Returns:
        Any | None: Cached payload on hit, otherwise ``None``.
    """
    if key in cache:
        # Retrieve the serialized object from cache
        data = cache.get(key)

        # Deserialize the object
        return pickle.loads(data)
