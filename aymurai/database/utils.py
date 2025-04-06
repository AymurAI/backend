import uuid
from hashlib import blake2b
from functools import cache

from pydantic import UUID5


@cache
def data_to_uuid(data: bytes) -> UUID5:
    h = blake2b(digest_size=16)
    h.update(data)

    return uuid.uuid5(uuid.NAMESPACE_DNS, h.hexdigest())


def text_to_uuid(text: str) -> UUID5:
    return data_to_uuid(text.encode("utf-8"))


def text_to_hash(text: str) -> str:
    h = blake2b(digest_size=16)
    h.update(text.encode("utf-8"))

    return h.hexdigest()
