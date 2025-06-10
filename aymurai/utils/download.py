import os

import gdown

from aymurai.logger import get_logger

NO_DOWNLOAD_IF_EXISTS = os.getenv("NO_DOWNLOAD_IF_EXISTS", True)

logger = get_logger(__name__)


def download(url, output):
    """
    Download file from url
    skip if file exists and environment variable NO_DOWNLOAD_IF_EXISTS is set to True

    Args:
        url (str): url to download
        output (str): output path

    Returns:
        str: output path
    """

    if os.path.exists(output) and bool(NO_DOWNLOAD_IF_EXISTS):
        logger.warn(
            "File found and skipping. Set NO_DOWNLOAD_IF_EXISTS environment to false to force download."
        )
        return output

    gdown.download(
        url,
        quiet=False,
        fuzzy=True,
        resume=True,
        output=output,
    )
    return output
