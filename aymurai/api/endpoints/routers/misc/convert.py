import os
import tempfile
import subprocess
from threading import Lock
from typing import Literal

import pymupdf4llm
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from md2docx_python.src.md2docx_python import markdown_to_word
from starlette.background import BackgroundTask

from aymurai.logger import get_logger
from aymurai.settings import settings

logger = get_logger(__name__)
pipeline_lock = Lock()

router = APIRouter()


def libreoffice_convert(
    input: str,
    format: Literal["pdf", "docx", "odt", "txt"],
    output_dir=tempfile.gettempdir(),
) -> str:
    cmd = f"{settings.LIBREOFFICE_BIN} --headless --convert-to {format} --outdir {output_dir} {input}"
    subprocess.run(cmd, shell=True, check=True)

    filename = os.path.basename(input)
    output = os.path.join(output_dir, filename.replace(input.split(".")[-1], format))

    if not os.path.exists(output):
        raise RuntimeError(f"LibreOffice conversion failed: {output}")

    return output


async def convert_common_txt_docx_doc(
    file: UploadFile,
    output_format: Literal["pdf", "docx", "odt"],
) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)

    tmp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    with open(tmp_file.name, "wb") as tmp:
        data = file.file.read()
        tmp.write(data)

    output = libreoffice_convert(tmp_file.name, format=output_format)
    os.remove(tmp_file.name)

    return FileResponse(
        output,
        background=BackgroundTask(os.remove, output),
        media_type="application/octet-stream",
        filename=os.path.basename(file.filename).replace(suffix, f".{output_format}"),
    )


async def convert_common_pdf(
    file: UploadFile,
    output_format: Literal["docx", "odt"],
) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Expected a .pdf file")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp_file:
        tmp_file.write(file.file.read())
        tmp_file.flush()

        text = pymupdf4llm.to_markdown(
            tmp_file.name,
            write_images=True,
            embed_images=True,
            image_size_limit=0,
        )

    tmp_file = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
    with open(tmp_file.name, "w") as f:
        f.write(text)
        f.flush()

    # NOTE: md2docx_python does not support images
    # FIXME: Use pandoc instead
    docx_name = tmp_file.name.replace(".md", ".docx")
    markdown_to_word(tmp_file.name, docx_name)
    os.remove(tmp_file.name)

    if output_format == "docx":
        return FileResponse(
            docx_name,
            background=BackgroundTask(os.remove, docx_name),
            media_type="application/octet-stream",
            filename=os.path.basename(file.filename).replace(".pdf", ".docx"),
        )

    output = libreoffice_convert(docx_name, format=output_format)
    os.remove(docx_name)

    return FileResponse(
        output,
        background=BackgroundTask(os.remove, output),
        media_type="application/octet-stream",
        filename=os.path.basename(file.filename).replace(".pdf", f".{output_format}"),
    )


# MARK: PDF -> ODT
@router.post("/convert/pdf/odt")
async def convert_pdf_odt(file: UploadFile) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Expected a .pdf file")

    return await convert_common_pdf(file, output_format="odt")


# MARK: PDF -> DOCX
@router.post("/convert/pdf/docx")
async def convert_pdf_docx(file: UploadFile) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Expected a .pdf file")

    return await convert_common_pdf(file, output_format="docx")


# MARK: DOCX -> ODT
@router.post("/convert/docx/odt")
async def convert_docx_odt(file: UploadFile) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    if suffix != ".docx":
        raise HTTPException(status_code=400, detail="Expected a .docx file")

    return await convert_common_txt_docx_doc(file, output_format="odt")


# MARK: DOCX -> PDF
@router.post("/convert/docx/pdf")
async def convert_docx_pdf(file: UploadFile) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    if suffix != ".docx":
        raise HTTPException(status_code=400, detail="Expected a .docx file")

    return await convert_common_txt_docx_doc(file, output_format="pdf")


# MARK: ODT -> PDF
@router.post("/convert/odt/pdf")
async def convert_odt_pdf(file: UploadFile) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    if suffix != ".odt":
        raise HTTPException(status_code=400, detail="Expected a .odt file")

    return await convert_common_txt_docx_doc(file, output_format="pdf")


# MARK: ODT -> DOCX
@router.post("/convert/odt/docx")
async def convert_odt_docx(file: UploadFile) -> FileResponse:
    _, suffix = os.path.splitext(file.filename)
    if suffix != ".odt":
        raise HTTPException(status_code=400, detail="Expected a .odt file")

    return await convert_common_txt_docx_doc(file, output_format="docx")


# # MARK: TXT -> DOCX
# @router.post("/convert/txt/docx")
# async def convert_txt_docx(file: UploadFile) -> FileResponse:
#     _, suffix = os.path.splitext(file.filename)
#     if suffix != ".txt":
#         raise HTTPException(status_code=400, detail="Expected a .txt file")

#     return await convert_common_txt_docx_doc(file, output_format="docx")


# # MARK: TXT -> ODT
# @router.post("/convert/txt/odt")
# async def convert_txt_odt(file: UploadFile) -> FileResponse:
#     _, suffix = os.path.splitext(file.filename)
#     if suffix != ".txt":
#         raise HTTPException(status_code=400, detail="Expected a .txt file")

#     return await convert_common_txt_docx_doc(file, output_format="odt")


# # MARK: TXT -> PDF
# @router.post("/convert/txt/pdf")
# async def convert_txt_pdf(file: UploadFile) -> FileResponse:
#     _, suffix = os.path.splitext(file.filename)
#     if suffix != ".txt":
#         raise HTTPException(status_code=400, detail="Expected a .txt file")

#     return await convert_common_txt_docx_doc(file, output_format="odt")
