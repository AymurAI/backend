import os
import subprocess
import tempfile
from functools import cache
from threading import Lock

import torch
from fastapi import Body, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from pydantic import UUID4
from sqlmodel import Session
from starlette.background import BackgroundTask

from aymurai.api.utils import load_pipeline
from aymurai.database.crud.model import register_model
from aymurai.database.crud.prediction import read_prediction_by_text, read_validation
from aymurai.database.schema import (
    Document,
    Model,
    Prediction,
    PredictionCreate,
    Paragraph,
)
from aymurai.database.session import get_session
from aymurai.database.utils import text_to_uuid
from aymurai.logger import get_logger
from aymurai.meta.api_interfaces import (
    DocLabel,
    DocumentInformation,
    TextRequest,
)
from aymurai.settings import settings
from aymurai.text.anonymization import DocAnonymizer
from aymurai.utils.misc import get_element

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH
torch.set_num_threads = 100  # FIXME: polemic ?
pipeline_lock = Lock()


router = APIRouter()


@cache
def get_model(session: Session = Depends(get_session)) -> Model:
    """
    Get the model from the database.

    Args:
        session (Session): Database session dependency.

    Returns:
        Model: The model from the database.
    """
    return register_model(
        model_name="flair-anonymizer",
        app_version=settings.APP_VERSION,
        session=session,
    )


# MARK: Document Compilation
@router.post("/document/{document_id}/compile", response_model=FileResponse)
async def anonymizer_compile_document(
    document_id: UUID4,
    session: Session = Depends(get_session),
    model: Model = Depends(get_model),
) -> FileResponse:
    """
    Compile Anonymized document from original file and annotations

    Args:
        file (UploadFile): Original file.
        annotations (str, optional): JSON with document annotations.

    Returns:
        FileResponse: Anonymized document
    """
    document = session.get(Document, document_id)

    # ———————— Sanity check ——————————————————————————————————————————————————————————
    # Check if the document exists
    if not document:
        raise ValueError(f"Document not found: {document_id}")

    ####################################################################################
    # Create a temporary file
    ####################################################################################

    filename = document.name
    logger.info(f"Document found: {document_id} ({filename})")

    # Create a temporary file
    _, suffix = os.path.splitext(filename)
    suffix = suffix if suffix == ".docx" else ".txt"
    tmp_dir = tempfile.gettempdir()

    # Use delete=False to avoid the file being deleted when the NamedTemporaryFile object is closed
    # This is necessary on Windows, as the file is locked by the file object and cannot be deleted
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=tmp_dir) as file:
        tmp_filename = file.name
        logger.info(f"saving temp file on local storage => {tmp_filename}")
        file.write(document.data)
        file.flush()
        file.close()

    logger.info(f"saved temp file on local storage => {tmp_filename}")

    ####################################################################################
    # Anonymize the document
    ####################################################################################
    doc_anonymizer = DocAnonymizer()

    if suffix == ".docx":
        item = {"path": tmp_filename}
        doc_anonymizer(
            item,
            [document_information.model_dump() for document_information in annotations],
            tmp_dir,
        )
        logger.info(f"saved temp file on local storage => {tmp_filename}")

    else:
        # Export as raw document
        anonymized_doc = [
            doc_anonymizer.replace_labels_in_text(document_information.model_dump())
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            for document_information in annotations
        ]
        with open(tmp_filename, "w") as f:
            f.write("\n".join(anonymized_doc))

    # Convert to ODT
    cmd = [
        settings.LIBREOFFICE_BIN,
        "--headless",
        "--convert-to",
        "odt",
        "--outdir",
        tmp_dir,
        tmp_filename,
    ]

    logger.info(f"Executing: {' '.join(cmd)}")

    try:
        output = subprocess.check_output(
            cmd, shell=False, encoding="utf-8", errors="ignore"
        )
        logger.info(f"LibreOffice output: {output}")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"LibreOffice conversion failed: {e.output.decode('utf-8', errors='ignore')}"
        )

    odt = tmp_filename.replace(suffix, ".odt")
    logger.info(f"Expected output file path: {odt}")

    if not os.path.exists(odt):
        raise RuntimeError(f"File at path {odt} does not exist.")

    # Ensure the temporary file is deleted
    os.remove(tmp_filename)

    return FileResponse(
        odt,
        background=BackgroundTask(os.remove, odt),
        media_type="application/octet-stream",
        filename=f"{os.path.splitext(filename)[0]}.odt",
    )
