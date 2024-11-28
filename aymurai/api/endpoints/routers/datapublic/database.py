import os
import tempfile

import pandas as pd
from sqlmodel import Session, select
from fastapi.routing import APIRouter
from fastapi import Depends, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from aymurai.logger import get_logger
from aymurai.database.schema import DataPublic
from aymurai.database.session import get_session
from aymurai.api.endpoints.meta.database import ExportFormat

logger = get_logger(__name__)


router = APIRouter()


@router.get("/export")
async def database_export(
    format: ExportFormat = ExportFormat.CSV,
    session: Session = Depends(get_session),
) -> FileResponse:
    statement = select(DataPublic)
    data = pd.read_sql(statement, session.bind)

    with tempfile.NamedTemporaryFile(delete=False) as temp:
        if format == ExportFormat.CSV:
            data.to_csv(temp.name, index=False)
            extension = "csv"
        elif format == ExportFormat.JSON:
            data.to_json(temp.name, orient="records")
            extension = "json"
        else:
            raise ValueError("Invalid export format")

        export_filename = temp.name

    return FileResponse(
        path=export_filename,
        filename=f"datapublic.{extension}",
        media_type="application/octet-stream",
        background=BackgroundTask(os.remove, export_filename),
    )


@router.post("/import")
async def database_import(
    csv: UploadFile,
    session: Session = Depends(get_session),
):
    pass
