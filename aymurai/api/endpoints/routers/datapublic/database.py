import os
import tempfile

import pandas as pd
from pydantic import UUID5
from sqlmodel import Session, select
from fastapi.routing import APIRouter
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from fastapi import Depends, UploadFile, HTTPException

from aymurai.logger import get_logger
from aymurai.database.schema import DataPublic
from aymurai.database.session import get_session
from aymurai.meta.api_interfaces import SuccessResponse
from aymurai.api.endpoints.meta.database import ExportFormat
from aymurai.database.meta.datapublic.model import DataPublicRead

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
            raise HTTPException(status_code=400, detail="Invalid export format")

        export_filename = temp.name

    return FileResponse(
        path=export_filename,
        filename=f"datapublic.{extension}",
        media_type="application/octet-stream",
        background=BackgroundTask(os.remove, export_filename),
    )


@router.post("/import", response_model=SuccessResponse)
async def database_import(
    csv: UploadFile,
    session: Session = Depends(get_session),
) -> SuccessResponse:
    with tempfile.NamedTemporaryFile(suffix=".csv") as tmp:
        data = csv.file.read()
        tmp.write(data)

        df = pd.read_csv(tmp.name)

    try:
        with session.begin():
            for _, row in df.iterrows():
                data = DataPublic(**row)
                session.add(data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SuccessResponse(message="Data imported successfully")


@router.get("/document/{document_id}", response_model=DataPublicRead)
async def datapublic_get_row(
    document_id: UUID5,
    session: Session = Depends(get_session),
) -> DataPublicRead:
    statement = select(DataPublic).where(DataPublic.id == document_id)
    data = session.exec(statement).first()

    if not data:
        raise HTTPException(status_code=404, detail="Document not found")

    return DataPublicRead.model_validate(data)
