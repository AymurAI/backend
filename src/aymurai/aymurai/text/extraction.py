import os
import logging
from zipfile import BadZipFile

import magic
import textract
from textract.exceptions import ShellError
from textract.parsers import _get_available_extensions

from aymurai.logging import get_logger
from aymurai.meta.pipeline_interfaces import Transform
from aymurai.utils.cache import cache_load, cache_save, get_cache_key

logger = get_logger(__file__)

TEXTRACT_EXTENSIONS = _get_available_extensions()
MIMETYPE_EXTENSION_MAPPER = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/pdf": "pdf",
}


ERRORS = ["ignore", "coerce", "raise"]


class InvalidFile(Exception):
    """Invalid File"""

    pass


class FulltextExtract(Transform):
    def __init__(self, use_cache: bool = False, **kwargs):
        self.use_cache = use_cache
        self.kwargs = kwargs

    def __call__(self, item: dict) -> dict:

        if not item.get("data"):
            item["data"] = {}

        cache_key = get_cache_key(item["path"], self.__name__)
        if self.use_cache and (cache_data := cache_load(key=cache_key)):
            text = cache_data
        else:
            text = extract_document(item["path"], **self.kwargs) or ""

        if self.use_cache:
            cache_save(text, key=cache_key)

        item["data"]["doc.text"] = text
        item["data"]["doc.valid"] = bool(len(text))

        return item


def get_extension(path: str) -> str:
    mimetype = magic.from_file(path, mime=True)
    return MIMETYPE_EXTENSION_MAPPER.get(mimetype, mimetype)


def extract_document(
    filename: str,
    errors: str = "ignore",
    **kwargs,
) -> str:
    """extract text from document by path

    Args:
        filename (str): document path
        errors (str, optional): {'ignore', 'raise', 'coerce'}, default 'ignore'
        - If :const:`'raise'`, then invalid parsing will raise an exception.
        - If :const:`'coerce'`, then invalid parsing will be set as :const:`NaN` and warn.
        - If :const:`'ignore'`, then invalid parsing will be set as :const:`NaN` but not warn.
        **kwargs: keyword arguments for textract.

    Raises:
        ValueError: Invalid argument
        InvalidFile: Invalid or unsupported file

    Returns:
        str: extracted document text
    """
    if errors not in ERRORS:
        raise ValueError(f"errors argument must be in {ERRORS}")

    ext = get_extension(filename)

    logger = get_logger(f"{__file__}.{__name__}")

    if errors == "ignore":
        logger.setLevel(logging.ERROR)

    if (
        not isinstance(filename, str)
        or not os.path.exists(filename)
        or ext not in TEXTRACT_EXTENSIONS
    ):
        if errors == "raise":
            raise InvalidFile(f"Invalid path: {filename}")
        logger.warn(f"skipping (invalid): {filename}")
        return

    try:
        docu = textract.process(filename, **kwargs).decode("utf-8")
    except (BadZipFile, KeyError, ShellError):
        if errors == "raise":
            raise
        logger.warn(f"skipping (corrupted): {filename}")
        docu = None

    return docu
