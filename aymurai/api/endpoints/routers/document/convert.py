import os
import subprocess
import tempfile
from enum import Enum
from typing import Literal

import pymupdf4llm
import pypandoc
from fastapi import HTTPException, Path, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from starlette import status
from starlette.background import BackgroundTask

from aymurai.logger import get_logger
from aymurai.settings import settings

logger = get_logger(__name__)
router = APIRouter()


class FileFormat(str, Enum):
    pdf = "pdf"
    docx = "docx"
    odt = "odt"


def libreoffice_convert(
    input: str,
    format: Literal["pdf", "docx", "odt", "txt"],
    output_dir=tempfile.gettempdir(),
    extra_args: str = "",
) -> str:
    cmd = f"{settings.LIBREOFFICE_BIN} --headless --convert-to {format} --outdir {output_dir} {input} {extra_args}"
    subprocess.run(cmd, shell=True, check=True)

    filename = os.path.basename(input)
    output = os.path.join(output_dir, filename.replace(input.split(".")[-1], format))

    if not os.path.exists(output):
        raise RuntimeError(f"LibreOffice conversion failed: {output}")

    return output


async def convert_libreoffice(
    file: UploadFile,
    output_format: Literal["pdf", "docx", "odt"],
    extra_args: str = "",
) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)

    tmp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    with open(tmp_file.name, "wb") as tmp:
        data = file.file.read()
        tmp.write(data)

    output = libreoffice_convert(
        tmp_file.name,
        format=output_format,
        extra_args=extra_args,
    )
    os.remove(tmp_file.name)

    return FileResponse(
        output,
        background=BackgroundTask(os.remove, output),
        media_type="application/octet-stream",
        filename=os.path.basename(file.filename).replace(suffix, f".{output_format}"),
    )


async def convert_pdf_pandoc(
    file: UploadFile,
    output_format: Literal["docx", "odt"],
) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    if suffix != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected a .pdf file",
        )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_file:
        tmp_file.write(file.file.read())
        tmp_file.flush()

        text = pymupdf4llm.to_markdown(
            tmp_file.name,
            write_images=True,
            embed_images=True,
            image_size_limit=0,
        )

    output = tempfile.mktemp(suffix=f".{output_format}")
    pypandoc.convert_text(text, output_format, format="md", outputfile=output)

    return FileResponse(
        output,
        background=BackgroundTask(os.remove, output),
        media_type="application/octet-stream",
        filename=os.path.basename(file.filename).replace(".pdf", f".{output_format}"),
    )


@router.post("/convert/{source}/{target}")
async def convert_file(
    file: UploadFile,
    source: FileFormat = Path(...),
    target: FileFormat = Path(...),
    backend: Literal["libreoffice", "pandoc"] = Query("libreoffice"),
) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    if suffix.lower() != f".{source.value}":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUES,
            detail=f"Expected a .{source.value} file",
        )
    if source == target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and target formats are the same.",
        )

    # Set extra_args for libreoffice conversions
    extra_args = '--infilter="writer_pdf_import"' if source == FileFormat.pdf else ""

    match (source, backend):
        case (FileFormat.pdf, "pandoc"):
            return await convert_pdf_pandoc(file, output_format=target.value)
        case (_, "libreoffice"):
            return await convert_libreoffice(
                file,
                output_format=target.value,
                extra_args=extra_args,
            )
        case _:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Conversion from {source.value} to {target.value} "
                    f"with backend {backend} is not supported."
                ),
            )
