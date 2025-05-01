import os
import re
import tempfile
from threading import Lock

from fastapi import Depends, UploadFile
from fastapi.routing import APIRouter
from more_itertools import unique_justseen
from sqlmodel import Session

from aymurai.api.utils import get_pipeline_doc_extract
from aymurai.database.schema import Paragraph, Document, DocumentPublic
from aymurai.database.session import get_session
from aymurai.database.utils import data_to_uuid
from aymurai.logger import get_logger

from aymurai.pipeline import AymurAIPipeline
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER
from aymurai.utils.misc import get_element

logger = get_logger(__name__)
pipeline_lock = Lock()

router = APIRouter()


@router.post("/document-extract", response_model=DocumentPublic)
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

            with pipeline_lock:
                processed = pipeline.preprocess([item])

        except Exception as e:
            logger.error(f"error while processing data item: {e}")
            raise e

    os.remove(tmp_filename)
    logger.info(f"removed temp file from local storage => {tmp_filename}")

    doc_text: str = get_element(processed[0], ["data", "doc.text"], "")

    paragraph_text = [text.strip() for text in doc_text.split("\n") if text.strip()]
    paragraph_text = [re.sub(r"\s{2,}", " ", text) for text in paragraph_text]
    paragraph_text = list(unique_justseen(paragraph_text))

    # Add paragraphs to the database
    # validation MUST be at least an empty list, to remember user feedback
    paragraphs = [
        Paragraph(text=paragraph, order=i) for i, paragraph in enumerate(paragraph_text)
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
