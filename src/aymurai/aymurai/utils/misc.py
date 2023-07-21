import re
from typing import Any, Union


def get_element(
    obj,
    levels: Union[list, Any] = [],
    default: Any = None,
    *,
    ignore_errors: bool = True
):
    """
    retrieve element hierarchically

    Args:
        obj (object): parent object to retrieve to
        levels (Union[list, Any], optional): hierarchy levels. Defaults to [].
        default (Any, optional): default value to return
        ignore_errors (str, optional): raise errors or ignore them. Defaults to True.

    Returns:
        _type_: element or None (in case child element doesnt exist and `ignore_errors=True`)
    """

    # if levels not a list handle it has a key
    if not isinstance(levels, list):
        levels = [levels]

    if not levels:
        return obj

    level = levels.pop(0)

    try:
        return get_element(obj[level], levels=levels)
    except Exception:
        if ignore_errors:
            return default
        else:
            raise


def is_url(text: str):
    match = re.findall(
        r"(http(s)?:\/\/.)(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)",
        text,
    )
    return bool(match)


# Taken from https://stackoverflow.com/a/20254842
def get_recursively(search_dict: dict, field: str) -> list:
    """
    Takes a dict with nested lists and dicts,
    and searches all dicts for a key of the field
    provided.
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
