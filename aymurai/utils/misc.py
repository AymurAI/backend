import re
from typing import Any


def get_element(
    obj: Any,
    levels: list[Any] | Any = [],
    default: Any = None,
    *,
    ignore_errors: bool = True,
) -> Any:
    """
    Retrieve an element from a nested object using hierarchical keys.

    Args:
        obj (Any): Parent object to traverse.
        levels (list[Any] | Any, optional): Hierarchy levels to access. Defaults to [].
        default (Any, optional): Value returned when traversal fails and
            `ignore_errors` is True. Defaults to None.
        ignore_errors (bool, optional): Whether to suppress lookup errors.
            Defaults to True.

    Returns:
        Any: Retrieved element, or `default` when traversal fails and
            `ignore_errors` is True.

    Raises:
        Exception: Propagates the underlying error when `ignore_errors` is False.
    """

    # if levels not a list handle it has a key
    if not isinstance(levels, list):
        levels = [levels]

    if not levels:
        return obj

    level = levels.pop(0)

    try:
        return get_element(obj[level], levels=levels, default=default)
    except Exception:
        if ignore_errors:
            return default
        else:
            raise


def is_url(text: str) -> bool:
    """
    Check whether a string contains a URL-like pattern.

    Args:
        text (str): Text to evaluate.

    Returns:
        bool: True when a URL-like pattern is found, otherwise False.
    """
    match = re.findall(
        r"(http(s)?:\/\/.)(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)",
        text,
    )
    return bool(match)


# Taken from https://stackoverflow.com/a/20254842
def get_recursively(search_dict: dict, field: str) -> list[Any]:
    """
    Search nested dictionaries and lists for values under a target key.

    Args:
        search_dict (dict): Dictionary to search recursively.
        field (str): Key name to collect.

    Returns:
        list[Any]: Values found for `field` across the nested structure.
    """
    fields_found = []

    for key, value in search_dict.items():
        if key == field:
            fields_found.append(value)

        elif isinstance(value, dict):
            results = get_recursively(value, field)
            for result in results:
                fields_found.append(result)

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    more_results = get_recursively(item, field)
                    for another_result in more_results:
                        fields_found.append(another_result)

    return fields_found
