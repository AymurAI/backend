# from: https://stackoverflow.com/a/23361323/4913438
import sys
import json
import decimal
import datetime

import pandas as pd
import numpy as np

from aymurai.logger import get_logger

logger = get_logger(__name__)


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
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
        try:
            if pd.isna(obj):
                return "null"
        except Exception:
            # Some container-like objects (e.g. arrays) are not valid for pd.isna checks.
            pass

        try:
            return super().default(obj)
        except:
            logger.error(f"Error trying to encode {obj}")
            raise


class EnhancedJSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, object_hook=self.object_hook, **kwargs)

    def object_hook(self, d):
        if "__type__" not in d:
            return d
        o = sys.modules[__name__]
        for e in d["__type__"].split("."):
            o = getattr(o, e)
        args, kwargs = d.get("args", ()), d.get("kwargs", {})
        return o(*args, **kwargs)
