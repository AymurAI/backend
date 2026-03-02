# from: https://stackoverflow.com/a/23361323/4913438
import sys
import json
import decimal
import datetime
from typing import Any

import pandas as pd

from aymurai.logger import get_logger

logger = get_logger(__name__)


class EnhancedJSONEncoder(json.JSONEncoder):
    """JSON encoder with support for datetime, timedelta, decimal, and NA values."""

    def default(self, obj: Any) -> Any:
        """
        Encode unsupported Python objects into JSON-serializable payloads.

        Args:
            obj (Any): Object to encode.

        Returns:
            Any: JSON-serializable representation of `obj`.

        Raises:
            TypeError: If `obj` cannot be encoded by the custom logic or parent
                JSON encoder.
        """
        if isinstance(obj, datetime.datetime):
            ARGS = ("year", "month", "day", "hour", "minute", "second", "microsecond")
            return {
                "__type__": "datetime.datetime",
                "args": [getattr(obj, a) for a in ARGS],
            }
        elif isinstance(obj, datetime.date):
            ARGS = ("year", "month", "day")
            return {
                "__type__": "datetime.date",
                "args": [getattr(obj, a) for a in ARGS],
            }
        elif isinstance(obj, datetime.time):
            ARGS = ("hour", "minute", "second", "microsecond")
            return {
                "__type__": "datetime.time",
                "args": [getattr(obj, a) for a in ARGS],
            }
        elif isinstance(obj, datetime.timedelta):
            ARGS = ("days", "seconds", "microseconds")
            return {
                "__type__": "datetime.timedelta",
                "args": [getattr(obj, a) for a in ARGS],
            }
        elif isinstance(obj, decimal.Decimal):
            return {
                "__type__": "decimal.Decimal",
                "args": [
                    str(obj),
                ],
            }
        elif pd.isna(obj):
            return "null"
        else:
            try:
                return super().default(obj)
            except:
                logger.error(f"Error trying to encode {obj}")
                raise


class EnhancedJSONDecoder(json.JSONDecoder):
    """JSON decoder that reconstructs objects serialized by `EnhancedJSONEncoder`."""

    def __init__(self, *args, **kwargs) -> None:
        """
        Initialize decoder with a custom object hook.

        Args:
            *args: Positional arguments forwarded to `json.JSONDecoder`.
            **kwargs: Keyword arguments forwarded to `json.JSONDecoder`.
        """
        super().__init__(*args, object_hook=self.object_hook, **kwargs)

    def object_hook(self, d: dict) -> Any:
        """
        Decode typed payloads into native Python objects.

        Args:
            d (dict): Decoded dictionary from JSON.

        Returns:
            Any: Reconstructed object when `__type__` is present, else `d`.
        """
        if "__type__" not in d:
            return d
        o = sys.modules[__name__]
        for e in d["__type__"].split("."):
            o = getattr(o, e)
        args, kwargs = d.get("args", ()), d.get("kwargs", {})
        return o(*args, **kwargs)
