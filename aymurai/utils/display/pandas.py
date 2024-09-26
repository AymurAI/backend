import pandas as pd
from more_itertools import flatten


def pandas_context(**kwargs):
    options = flatten(kwargs.items())
    return pd.option_context(*options)  # type: ignore
