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
