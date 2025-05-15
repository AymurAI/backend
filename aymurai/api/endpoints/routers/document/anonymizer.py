import os
import subprocess
import tempfile

from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from pydantic import UUID4, UUID5
from sqlmodel import Session
from starlette.background import BackgroundTask

from aymurai.database.crud.prediction import read_document_prediction_paragraphs
from aymurai.database.schema import Document, ModelType
from aymurai.database.session import get_session
from aymurai.logger import get_logger
from aymurai.settings import settings
from aymurai.text.anonymization.alignment import replace_labels_in_text
from aymurai.text.anonymization.core import anonymize_docx

logger = get_logger(__name__)


router = APIRouter()


# MARK: Document Compilation
@router.get(
    f"/document/{{document_id}}/pipeline/{ModelType.ANONYMIZATION}/compile",
    response_class=FileResponse,
)
async def anonymizer_compile_document(
    document_id: UUID4 | UUID5,
    session: Session = Depends(get_session),
) -> FileResponse:
    """
    Compile Anonymized document from original file and annotations

    Args:
        document_id (UUID4): The ID of the document to be compiled.
        session (Session): Database session dependency.

    Returns:
        FileResponse: Anonymized document
    """
    document = session.get(Document, document_id)

    # ———————— Sanity check ———————————————————————————————————————————————————————————
    # Check if the document exists
    if not document:
        raise ValueError(f"Document not found: {document_id}")

    # ———————— Get annotations ————————————————————————————————————————————————————————
    annotations = read_document_prediction_paragraphs(
        session=session,
        document_id=document_id,
        model_type=ModelType.ANONYMIZATION,
    )

    # ======== Document Anonymization =================================================
    # ———————— Create temporary file ——————————————————————————————————————————————————
    filename = document.name
    logger.info(f"Document found: {document_id} ({filename})")

    # Create a temporary file
    _, suffix = os.path.splitext(filename)
    suffix = suffix.lower()
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

    # ———————— Anonymize document —————————————————————————————————————————————————————

    if suffix == ".docx":
        anonymize_docx(
            path=tmp_filename, paragraph_preds=annotations, output_dir=tmp_dir
        )
        logger.info(f"saved temp file on local storage => {tmp_filename}")

    else:
        # Export as raw document
        anonymized_doc = [
            replace_labels_in_text(text=paragraph.text, prediction=paragraph.prediction)
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            for paragraph in annotations
        ]
        with open(tmp_filename, "w") as f:
            f.write("\n".join(anonymized_doc))

    # ——————— Convert to ODT ——————————————————————————————————————————————————————————
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
