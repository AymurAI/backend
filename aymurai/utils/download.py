import os
import shutil
import tempfile
from pathlib import Path

import requests

from aymurai.logger import get_logger

NO_DOWNLOAD_IF_EXISTS = os.getenv("NO_DOWNLOAD_IF_EXISTS", True)

logger = get_logger(__name__)


def download(url: str, output: str) -> str:
    """
    Stream download to a file.

    Skips download when the target exists and NO_DOWNLOAD_IF_EXISTS is truthy.

    Args:
        url (str): URL to download.
        output (str): Path to save the downloaded file.

    Returns:
        str: Path to the downloaded file.

    Raises:
        requests.HTTPError: If the download request returns an HTTP error status.
    """

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and NO_DOWNLOAD_IF_EXISTS:
        logger.warning(
            "File found and skipping. Set NO_DOWNLOAD_IF_EXISTS environment to false to force download."
        )
        return str(output_path)

    logger.info(f"Downloading {url} -> {output_path}")
    with requests.get(url, stream=True, allow_redirects=True, timeout=60) as resp:
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            tmp_path = Path(tmp.name)
    shutil.move(tmp_path, output_path)
    return str(output_path)
