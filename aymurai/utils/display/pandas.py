from typing import ContextManager

import pandas as pd
from more_itertools import flatten


def pandas_context(**kwargs) -> ContextManager[None]:
    """
    Build a pandas option context manager from keyword options.

    Args:
        **kwargs: Pandas option names mapped to values.

    Returns:
        ContextManager[None]: Context manager that applies the provided options.
    """
    options = flatten(kwargs.items())
    return pd.option_context(*options)  # type: ignore
