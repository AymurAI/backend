import uuid
from hashlib import blake2b


def text_to_uuid(text: str) -> uuid.UUID:
    h = blake2b(digest_size=16)
    h.update(text.encode("utf-8"))

    return uuid.uuid5(uuid.NAMESPACE_DNS, h.hexdigest())
