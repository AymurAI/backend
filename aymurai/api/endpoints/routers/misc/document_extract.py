import concurrent.futures
import os
import re
import tempfile

from fastapi import HTTPException, UploadFile
from fastapi.routing import APIRouter
from more_itertools import unique_justseen
from starlette import status

from aymurai.database.utils import data_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import Document
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER, extract_document
from aymurai.text.normalize import document_normalize

logger = get_logger(__name__)

router = APIRouter()


def extraction(path: str) -> str:
    """
    Wrapper function to call the extract_document function.
    This is necessary to ensure that the function can be pickled and run in a separate process.

    Args:
        path (str): Path to the file to be processed.

    Returns:
        str: Extracted text from the document.
    """
    text = extract_document(path)
    return document_normalize(text, preserve_paragraphs=True) if text else ""


def run_safe_text_extraction(path: str, timeout_s: float | None = 300) -> str:
    """
    Runs the text extraction in a separate process to avoid blocking the main thread.
    This is useful for long-running tasks or when the extraction might hang.

    Args:
        path (str): Path to the file to be processed.
        timeout_s (float | None): Timeout in seconds for the extraction process.
            If None, waits indefinitely. Defaults to 300.

    Returns:
        str: Extracted text from the document.

    Raises:
        TimeoutError: If the extraction process exceeds the specified timeout.
    """
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(extraction, path)
        try:
            return future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            # Cancel/killing the subprocess
            future.cancel()
            raise


def _split_document_paragraphs(document: str) -> list[str]:
    if re.search(r"\n\s*\n+", document):
        raw_paragraphs = re.split(r"\n\s*\n+", document)
    else:
        raw_paragraphs = document.splitlines()

    paragraphs = [
        re.sub(r"[ \t]{2,}", " ", paragraph.strip())
        for paragraph in raw_paragraphs
        if paragraph.strip()
    ]
    return list(unique_justseen(paragraphs))


@router.post("/document-extract", response_model=Document)
def plain_text_extractor(file: UploadFile) -> Document:
    """
    Extract plain text from an uploaded document.

    Args:
        file (UploadFile): Incoming document upload.

    Returns:
        Document: Extracted and normalized document payload.
    """
    logger.info(f"receiving => {file.filename}")
    extension = MIMETYPE_EXTENSION_MAPPER.get(file.content_type)
    logger.info(f"detected extension: {extension} ({file.content_type})")

    data = file.file.read()

    # Use delete=False to avoid the file being deleted when the NamedTemporaryFile object is closed
    # This is necessary on Windows, as the file is locked by the file object and cannot be deleted
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp_file:
        try:
            tmp_filename = tmp_file.name
            tmp_file.write(data)
            tmp_file.flush()
            tmp_file.close()

            logger.info(f"saved temp file on local storage => {tmp_filename}")

            document = run_safe_text_extraction(tmp_filename)

        except concurrent.futures.TimeoutError:
            logger.error(f"Timeout while extracting text from {file.filename}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Text extraction timed out",
            )

        except Exception as e:
            logger.error(f"error while processing data item: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    os.remove(tmp_filename)
    logger.info(f"removed temp file from local storage => {tmp_filename}")

    document_id = data_to_uuid(data)
    paragraphs = _split_document_paragraphs(document)

    return Document(document=paragraphs, document_id=document_id)
