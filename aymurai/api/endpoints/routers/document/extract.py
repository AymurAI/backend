import concurrent.futures
import os
import re
import tempfile

from fastapi import Depends, HTTPException, UploadFile
from fastapi.routing import APIRouter
from more_itertools import unique_justseen
from sqlmodel import Session
from starlette import status

from aymurai.api.utils import get_pipeline_doc_extract
from aymurai.database.schema import Document, DocumentPublic, Paragraph
from aymurai.database.session import get_session
from aymurai.database.utils import data_to_uuid
from aymurai.logger import get_logger
from aymurai.pipeline import AymurAIPipeline
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER, extract_document
from aymurai.text.normalize import document_normalize

logger = get_logger(__name__)

router = APIRouter()


def extraction(path: str) -> str:
    """
    Wrapper function to call the extract_document function.
    This is necessary to ensure that the function can be pickled and run in a separate process.
    """
    text = extract_document(path)
    return document_normalize(text) if text else ""


def run_safe_text_extraction(path: str, timeout_s: float = 5) -> str:
    """
    Runs the text extraction in a separate process to avoid blocking the main thread.
    This is useful for long-running tasks or when the extraction might hang.
    Args:
        path (str): Path to the file to be processed.
        timeout_s (float): Timeout in seconds for the extraction process.
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


@router.post("/extract", response_model=DocumentPublic)
def plain_text_extractor(
    file: UploadFile,
    pipeline: AymurAIPipeline = Depends(get_pipeline_doc_extract),
    session: Session = Depends(get_session),
    use_cache: bool = True,
) -> DocumentPublic:
    logger.info(f"receiving => {file.filename}")
    extension = MIMETYPE_EXTENSION_MAPPER.get(file.content_type)
    logger.info(f"detected extension: {extension} ({file.content_type})")

    data = file.file.read()
    document_id = data_to_uuid(data)

    document = session.get(Document, document_id)
    if document and use_cache:
        logger.warning(f"Document already exists: {document_id}. skipping creation.")
        return document

    # Use delete=False to avoid the file being deleted when the NamedTemporaryFile object is closed
    # This is necessary on Windows, as the file is locked by the file object and cannot be deleted
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp_file:
        try:
            tmp_filename = tmp_file.name
            tmp_file.write(data)
            tmp_file.flush()
            tmp_file.close()

            logger.info(f"saved temp file on local storage => {tmp_filename}")

            item = {"path": tmp_filename}

            logger.info("processing data item")
            logger.info(f"{item}")

            document = run_safe_text_extraction(tmp_filename, timeout_s=5)

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

    paragraph_text = [text.strip() for text in document.split("\n") if text.strip()]
    paragraph_text = [re.sub(r"\s{2,}", " ", text) for text in paragraph_text]
    paragraph_text = list(unique_justseen(paragraph_text))

    # Add paragraphs to the database
    # validation MUST be at least an empty list, to remember user feedback
    paragraphs = [
        Paragraph(text=paragraph, index=i) for i, paragraph in enumerate(paragraph_text)
    ]

    paragraph_text = Document(
        id=document_id,
        data=data,
        name=file.filename,
        paragraphs=paragraphs,
    )

    session.add_all([paragraph_text] + paragraphs)
    session.commit()
    session.refresh(paragraph_text)

    return paragraph_text
