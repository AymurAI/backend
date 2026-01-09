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


def extraction(
    path: str,
    use_cache: bool = True,
    **kwargs,
) -> str:
    """
    Wrapper function to call the extract_document function.
    This is necessary to ensure that the function can be pickled and run in a separate process.

    Args:
        path (str): Path to the file to be processed.
        use_cache (bool): Whether to use caching for the extraction.
        **kwargs: Extractor-specific configuration overrides.

    Returns:
        str: Extracted text from the document.
    """
    text = extract_document(path, use_cache=use_cache, **kwargs)
    return document_normalize(text) if text else ""


def run_safe_text_extraction(
    path: str,
    timeout_s: float | None = None,
    use_cache: bool = True,
    **kwargs,
) -> str:
    """
    Runs the text extraction in a separate process to avoid blocking the main thread.
    This is useful for long-running tasks or when the extraction might hang.

    Args:
        path (str): Path to the file to be processed.
        timeout_s (float | None): Timeout in seconds for the extraction process.
            If None, waits indefinitely. Defaults to None.
        use_cache (bool): Whether to use caching for the extraction.
        **kwargs: Extractor-specific configuration overrides.

    Returns:
        str: Extracted text from the document.

    Raises:
        TimeoutError: If the extraction process exceeds the specified timeout.
    """
    with concurrent.futures.ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(extraction, path, use_cache, **kwargs)
        try:
            return future.result(timeout=timeout_s)
        except concurrent.futures.TimeoutError:
            # Cancel/killing the subprocess
            future.cancel()
            raise


@router.post("/document-extract", response_model=Document)
def plain_text_extractor(
    file: UploadFile,
    use_cache: bool = True,
    layout_batch_size: int = 8,
    detection_batch_size: int = 8,
    table_rec_batch_size: int = 8,
    recognition_batch_size: int = 8,
    ocr_error_batch_size: int = 8,
    force_ocr: bool = False,
    strip_existing_ocr: bool = True,
    torch_device: str | None = None,
    debug: bool | None = None,
) -> Document:
    """
    Extract plain text from an uploaded document.

    Args:
        file (UploadFile): Incoming document upload.
        use_cache (bool): Whether to use caching for the extraction. Defaults to True.
        layout_batch_size (int): Batch size for layout model inference. Defaults to 8.
        detection_batch_size (int): Batch size for detection model inference. Defaults to 8.
        table_rec_batch_size (int): Batch size for table recognition. Defaults to 8.
        recognition_batch_size (int): Batch size for OCR recognition. Defaults to 8.
        ocr_error_batch_size (int): Batch size for OCR error correction. Defaults to 8.
        force_ocr (bool): Force OCR even if text is detected. Defaults to False.
        strip_existing_ocr (bool): Remove embedded OCR layers before re-OCR. Defaults to True.
        torch_device (str | None): Optional override for the torch device. Defaults to None.
        debug (bool | None): Optional override for marker debug mode. Defaults to None.

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

            document = run_safe_text_extraction(
                tmp_filename,
                use_cache=use_cache,
                layout_batch_size=layout_batch_size,
                detection_batch_size=detection_batch_size,
                table_rec_batch_size=table_rec_batch_size,
                recognition_batch_size=recognition_batch_size,
                ocr_error_batch_size=ocr_error_batch_size,
                force_ocr=force_ocr,
                strip_existing_ocr=strip_existing_ocr,
                torch_device=torch_device,
                debug=debug,
            )

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

    paragraphs = [line.strip() for line in document.split("\n") if line.strip()]
    paragraphs = [re.sub(r"\s{2,}", " ", line) for line in paragraphs]
    paragraphs = list(unique_justseen(paragraphs))

    return Document(document=paragraphs, document_id=document_id)
