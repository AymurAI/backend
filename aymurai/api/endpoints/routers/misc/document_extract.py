import os
import re
import tempfile
from threading import Lock

from fastapi import Depends, UploadFile
from fastapi.routing import APIRouter
from more_itertools import unique_justseen

from aymurai.api.utils import get_pipeline_doc_extract
from aymurai.database.utils import data_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import Document
from aymurai.pipeline import AymurAIPipeline
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER
from aymurai.utils.misc import get_element

logger = get_logger(__name__)
pipeline_lock = Lock()

router = APIRouter()


@router.post("/document-extract", response_model=Document)
def plain_text_extractor(
    file: UploadFile,
    pipeline: AymurAIPipeline = Depends(get_pipeline_doc_extract),
) -> Document:
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

            item = {"path": tmp_filename}

            logger.info("processing data item")
            logger.info(f"{item}")

            with pipeline_lock:
                processed = pipeline.preprocess([item])

        except Exception as e:
            logger.error(f"error while processing data item: {e}")
            raise e

    os.remove(tmp_filename)
    logger.info(f"removed temp file from local storage => {tmp_filename}")

    document_id = data_to_uuid(data)
    doc_text: str = get_element(processed[0], ["data", "doc.text"], "")

    document = [text.strip() for text in doc_text.split("\n") if text.strip()]
    document = [re.sub(r"\s{2,}", "", text) for text in document]
    document = list(unique_justseen(document))

    return Document(document=document, document_id=document_id)
