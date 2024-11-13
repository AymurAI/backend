import os
import json
import tempfile
from subprocess import getoutput

from sqlmodel import Session, select
from fastapi.routing import APIRouter
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from fastapi import Body, Form, Depends, UploadFile

from aymurai.logger import get_logger
from aymurai.database.session import get_session
from aymurai.text.anonymization import DocAnonymizer
from aymurai.database.utils import data_to_uuid, text_to_uuid
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER
from aymurai.meta.api_interfaces import DocLabel, DocumentAnnotations
from aymurai.database.schema import AnonymizationDocument, AnonymizationParagraph

logger = get_logger(__name__)


router = APIRouter()


@router.post("/document")
async def anonymize_document(
    file: UploadFile,
    annotations: str = Form(...),
    session: Session = Depends(get_session),
) -> FileResponse:
    logger.info(f"receiving => {file.filename}")
    extension = MIMETYPE_EXTENSION_MAPPER.get(file.content_type)
    logger.info(f"detection extension: {extension} ({file.content_type})")

    tmp_filename = f"/tmp/{file.filename}"
    logger.info(f"saving temp file on local storage => {tmp_filename}")
    with open(tmp_filename, "wb") as tmp_file:
        data = file.file.read()
        tmp_file.write(data)
    logger.info(f"saved temp file on local storage => {tmp_filename}")

    annots = json.loads(annotations)
    annots = DocumentAnnotations(**annots)
    logger.info(f"processing annotations => {annots}")

    # Add paragraphs to the database
    paragraphs = [
        AnonymizationParagraph(text=paragraph.document, validation=paragraph.labels)
        for paragraph in annots.data
    ]
    session.add_all(paragraphs)
    session.commit()

    # Add document to the database
    document = AnonymizationDocument(
        id=data_to_uuid(data),
        name=file.filename,
        paragraphs=paragraphs,
    )
    session.add(document)
    session.commit()

    # Anonymize the document
    doc_anonymizer = DocAnonymizer()

    item = {"path": tmp_filename}
    doc_anonymizer(
        item,
        [document_information.model_dump() for document_information in annots.data],
        "/tmp",
    )
    logger.info(f"saved temp file on local storage => {tmp_filename}")

    # Connvert to ODT
    with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".docx") as temp:
        with open(tmp_filename, "rb") as f:
            temp.write(f.read())

        temp.flush()

        cmd = "libreoffice --headless --convert-to odt --outdir /tmp {file}"
        getoutput(cmd.format(file=temp.name))
        odt = temp.name.replace(".docx", ".odt")

        os.remove(tmp_filename)

        return FileResponse(
            odt,
            background=BackgroundTask(os.remove, odt),
            media_type="application/octet-stream",
            filename=f"{os.path.splitext(os.path.basename(tmp_filename))[0]}.odt",
        )


@router.post("/validation", response_model=list[DocLabel] | None)
async def get_paragraph_validation(
    text: str = Body(...),
    db: Session = Depends(get_session),
) -> list[DocLabel] | None:
    """
    Get the validation labels for a given paragraph text.
    """

    paragraph_id = text_to_uuid(text)

    statement = select(AnonymizationParagraph).where(
        AnonymizationParagraph.id == paragraph_id
    )
    paragraph = db.exec(statement).first()

    if not paragraph:
        return None

    return paragraph.validation
