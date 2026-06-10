import mimetypes
import os
import zipfile
from pathlib import Path
from zipfile import BadZipFile

from aymurai.logger import get_logger
from aymurai.text.extractors import SUPPORTED_EXTENSIONS, InvalidFile, get_extractor

logger = get_logger(__file__)

MIMETYPE_EXTENSION_MAPPER = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.oasis.opendocument.text": "odt",
    "application/pdf": "pdf",
}


ERRORS = ["ignore", "coerce", "raise"]


def _zip_contains(path: str, member: str) -> bool:
    """
    Check if a zip file contains a specific member.

    Args:
        path (str): Path to the zip file.
        member (str): Member name to check for.

    Returns:
        bool: True if the member exists in the zip file, False otherwise.
    """
    try:
        with zipfile.ZipFile(path, "r") as archive:
            return member in archive.namelist()

    except (FileNotFoundError, PermissionError, OSError) as exc:
        logger.warning("Cannot access '%s': %s", path, exc)

    except BadZipFile as exc:
        logger.warning("Invalid zip structure for '%s': %s", path, exc)

    return False


def get_extension(path: str) -> str:
    # First, try by extension
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        try:
            with open(path, "rb") as file_handle:
                header = file_handle.read(1024)

        except (FileNotFoundError, PermissionError, OSError) as exc:
            logger.warning("Cannot open '%s': %s", path, exc)

        else:
            # PDF header check: scan for %PDF within the first 1KB
            if b"%PDF" in header:
                return "pdf"

    if ext == ".docx" and _zip_contains(path, "word/document.xml"):
        return "docx"

    if ext == ".odt" and _zip_contains(path, "content.xml"):
        return "odt"

    # Fallback to mimetypes
    mimetype, _ = mimetypes.guess_type(path)
    if mimetype in MIMETYPE_EXTENSION_MAPPER:
        return MIMETYPE_EXTENSION_MAPPER[mimetype]

    if ext:
        logger.debug("Falling back to raw extension for '%s'", path)
        return ext[1:]

    logger.warning("Unable to identify file type for '%s'", path)
    return "unknown"


def extract_document(
    filename: str | Path,
    errors: str = "ignore",
    use_cache: bool = True,
    **kwargs,
) -> str | None:
    """
    Extract text from document by path.

    Args:
        filename (str): document path.
        errors (str, optional): {'ignore', 'raise', 'coerce'}, default 'ignore'
        - If :const:`'raise'`, then invalid parsing will raise an exception.
        - If :const:`'coerce'`, then invalid parsing will be setas :const:`NaN`
            and warn.
        - If :const:`'ignore'`, then invalid parsing will be set as :const:`NaN`
            but not warn.
        use_cache (bool, optional): Toggle extractor-level caching. Defaults to True.
        **kwargs: keyword arguments for text extractors.

    Raises:
        ValueError: Invalid argument.
        InvalidFile: Invalid or unsupported file.

    Returns:
        str: extracted document text.
    """
    filename = str(filename)

    if errors not in ERRORS:
        raise ValueError(f"errors argument must be in {ERRORS}")

    ext = get_extension(filename)

    if (not isinstance(filename, str)) or not os.path.exists(filename):
        if errors == "raise":
            raise InvalidFile(f"Invalid path: {filename}")
        logger.warning("Skipping (missing): %s", filename)
        return None

    if ext not in SUPPORTED_EXTENSIONS:
        if errors == "raise":
            raise InvalidFile(f"Unsupported extension: {ext}")
        logger.warning("Skipping (unsupported %s): %s", ext, filename)
        return None

    extractor = get_extractor(ext)

    try:
        return extractor.extract(Path(filename), use_cache=use_cache, **kwargs)
    except InvalidFile as exc:
        if errors == "raise":
            raise
        logger.warning("Skipping (corrupted): %s (%s)", filename, exc)
        return None
    except BadZipFile as exc:
        if errors == "raise":
            raise
        logger.warning("Skipping (corrupted archive): %s (%s)", filename, exc)
        return None
    except Exception as exc:
        if errors == "raise":
            raise
        logger.warning("Skipping (unexpected): %s (%s)", filename, exc)
        return None
