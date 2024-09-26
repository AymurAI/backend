import pickle

from typing import Any


def save_pickle(object_: Any, output_path: str):
    with open(output_path, "wb") as f:
        pickle.dump(object_, f)


def load_pickle(input_path: str) -> Any:
    with (open(input_path, "rb")) as f:
        object_ = pickle.load(f)
        return object_
