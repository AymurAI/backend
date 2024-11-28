import os
import tempfile
from threading import Lock

from fastapi.routing import APIRouter
from fastapi import Depends, UploadFile

from aymurai.logger import get_logger
from aymurai.utils.misc import get_element
from aymurai.pipeline import AymurAIPipeline
from aymurai.meta.api_interfaces import Document
from aymurai.api.utils import get_pipeline_doc_extract
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER

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

    candidate = next(tempfile._get_candidate_names())
    tmp_filename = f"/tmp/{candidate}.{extension}"
    logger.info(f"saving temp file on local storage => {tmp_filename}")
    with open(tmp_filename, "wb") as tmp_file:
        data = file.file.read()
        tmp_file.write(data)  # async write
    logger.info(f"saved temp file on local storage => {tmp_filename}")

    item = {
        "path": tmp_filename,
    }

    logger.info("processing data item")
    logger.info(f"{item}")
    with pipeline_lock:
        processed = pipeline.preprocess([item])

    logger.info(f"{processed}")

    logger.info(f"removing file => {tmp_filename}")
    os.remove(tmp_filename)
    doc_text = get_element(processed[0], ["data", "doc.text"], "")

    return Document(
        document=[text.strip() for text in doc_text.split("\n") if text.strip()],
    )
