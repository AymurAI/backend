import json
from itertools import groupby
from typing import Union, Iterable, Iterator


def save_json(json_data: Union[dict, list[dict]], file_path: str):
    with open(file_path, "w") as f:
        f.write(json.dumps(json_data, indent=4, ensure_ascii=False))


def load_json(json_file_path: str) -> Union[dict, list[dict]]:
    with open(json_file_path, "r") as f:
        content = json.loads(f.read())
        return content


def get_unique(json_list: list[dict]) -> Iterator[dict]:
    unique = set(map(json.dumps, json_list))
    unique = map(json.loads, unique)
    return unique


def group_by_key(
    json_iter: Iterable[dict], group_key: str, sort_key: str = ""
) -> Iterator[list[dict]]:

    if sort_key:
        json_iter = sorted(json_iter, key=lambda x: x[sort_key])

    groups = map(lambda x: list(x[1]), groupby(json_iter, lambda x: x[group_key]))

    return groups
