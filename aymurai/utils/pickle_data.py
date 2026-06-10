import pickle

from typing import Any


def save_pickle(object_: Any, output_path: str) -> None:
    """
    Serialize and save a Python object to a pickle file.

    Args:
        object_ (Any): Object to serialize.
        output_path (str): Output file path.
    """
    with open(output_path, "wb") as f:
        pickle.dump(object_, f)


def load_pickle(input_path: str) -> Any:
    """
    Load and deserialize a Python object from a pickle file.

    Args:
        input_path (str): Input file path.

    Returns:
        Any: Deserialized Python object.
    """
    with (open(input_path, "rb")) as f:
        object_ = pickle.load(f)
        return object_
