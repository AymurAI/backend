import os
import tempfile
import subprocess
from enum import Enum
from threading import Lock

from fastapi import UploadFile
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from starlette.background import BackgroundTask

from aymurai.api.exceptions import UnsupportedFileType
from aymurai.logger import get_logger
from aymurai.settings import settings
from aymurai.text.extraction import pdf_to_text

logger = get_logger(__name__)
pipeline_lock = Lock()

router = APIRouter()


class InputFormat(str, Enum):
    docx = "docx"
    odt = "odt"
    pdf = "pdf"
    txt = "txt"


class OutputFormat(str, Enum):
    docx = "docx"
    odt = "odt"
    pdf = "pdf"


class ValidPair(Enum):
    docx_odt = ("docx", "odt")
    docx_pdf = ("docx", "pdf")
    odt_docx = ("odt", "docx")
    odt_pdf = ("odt", "pdf")
    # pdf_docx = ("pdf", "docx")
    # pdf_odt = ("pdf", "odt")

    def __str__(self):
        return f"{self.name}"


def libreoffice_convert(
    input: str, format: OutputFormat, output_dir=tempfile.gettempdir()
) -> str:
    cmd = f"{settings.LIBREOFFICE_BIN} --headless --convert-to {format} --outdir {output_dir} {input}"
    subprocess.run(cmd, shell=True, check=True)

    filename = os.path.basename(input)
    output = os.path.join(output_dir, filename.replace(input.split(".")[-1], format))

    if not os.path.exists(output):
        raise RuntimeError(f"LibreOffice conversion failed: {output}")

    return output


@router.post("/file_convert")
def convert_file(file: UploadFile, format: OutputFormat = "odt") -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    input_format = suffix[1:]
    if input_format not in InputFormat.__members__:
        raise UnsupportedFileType(detail=f"Unsupported file type: {suffix}")

    tmp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    with open(tmp_file.name, "wb") as tmp:
        data = file.file.read()
        tmp.write(data)

    if input_format == InputFormat.pdf:
        # Convert PDF to TXT
        text = pdf_to_text(tmp_file.name)
        with open(tmp_file.name, "w") as tmp:
            tmp.write(text)

        new_name = tmp_file.name.replace(".pdf", ".txt")
        os.rename(tmp_file.name, new_name)
        tmp_file.name = new_name

    output = libreoffice_convert(tmp_file.name, format=format)
    os.remove(tmp_file.name)

    return FileResponse(
        output,
        background=BackgroundTask(os.remove, output),
        media_type="application/octet-stream",
        filename=os.path.basename(output),
    )
