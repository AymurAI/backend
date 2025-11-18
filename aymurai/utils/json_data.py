import json
from datetime import date, datetime
from itertools import groupby
from typing import Any, Iterable, Iterator


def json_serial(obj: Any) -> str:
    """
    JSON serializer for objects not serializable by default JSON encoder.

    Args:
        obj: The object to serialize. This function currently supports
             datetime.date and datetime.datetime objects.

    Returns:
        str: The ISO 8601 formatted string representation of the date or datetime object.

    Raises:
        TypeError: If the object is not of type datetime.date or datetime.datetime.
    """  # noqa: E501
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def get_pretty(obj: dict | list[Any]) -> str:
    """
    Returns a pretty json string.

    Args:
        obj (Union[dict, list[Any]]): the object to be converted to json.

    Returns:
        str: the pretty json string.
    """
    pretty_json_str = json.dumps(obj, indent=4, ensure_ascii=False, default=json_serial)
    return pretty_json_str


def save_json(json_data: dict | list[dict], file_path: str) -> None:
    """

    Saves a JSON object to a file.

    Args:
        json_data (dict | list[dict]): The JSON data to be saved.
        file_path (str): The path to the file where the JSON data will be saved.
    """
    with open(file_path, "w") as f:
        f.write(json.dumps(json_data, indent=4, ensure_ascii=False))


def load_json(json_file_path: str) -> dict | list[dict]:
    """
    Loads a JSON object from a file.

    Args:
        json_file_path (str): The path to the JSON file.

    Returns:
        dict | list[dict]: The loaded JSON object.
    """
    with open(json_file_path, "r") as f:
        content = json.loads(f.read())
        return content


def get_unique(json_list: list[dict]) -> Iterator[dict]:
    """
    Get unique json objects from a list of json objects.

    Args:
        json_list (list[dict]):  The list of JSON objects.

    Returns:
        Iterator[dict]: An iterator of unique JSON objects.
    """
    unique = set(map(json.dumps, json_list))
    unique = map(json.loads, unique)
    return unique


def group_by_key(
    json_iter: Iterable[dict], group_key: str, sort_key: str = ""
) -> Iterator[list[dict]]:
    """
    Groups a list of JSON objects by a specified key.

    Args:
        json_iter (Iterable[dict]): An iterable of JSON objects to be grouped.
        group_key (str): The key to group the JSON objects by.
        sort_key (str, optional): An optional key to sort the JSON objects before grouping.
                                  Defaults to "".

    Returns:
        Iterator[list[dict]]: An iterator of lists of JSON objects grouped by the specified key.
    """
    if sort_key:
        json_iter = sorted(json_iter, key=lambda x: x[sort_key])

    groups = map(lambda x: list(x[1]), groupby(json_iter, lambda x: x[group_key]))

    return groups
