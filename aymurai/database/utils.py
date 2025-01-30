import uuid
from hashlib import blake2b


def data_to_uuid(data: bytes) -> uuid.UUID:
    h = blake2b(digest_size=16)
    h.update(data)

    return uuid.uuid5(uuid.NAMESPACE_DNS, h.hexdigest())


def text_to_uuid(text: str) -> uuid.UUID:
    return data_to_uuid(text.encode("utf-8"))
