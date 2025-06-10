import os
import json
import tempfile

import pandas as pd
from pydantic import UUID4, UUID5
from sqlmodel import Session, select
from fastapi.routing import APIRouter
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from fastapi import Depends, UploadFile, HTTPException

from aymurai.logger import get_logger
from aymurai.database.session import get_session
from aymurai.meta.api_interfaces import SuccessResponse
from aymurai.api.endpoints.meta.database import ExportFormat
from aymurai.database.schema import (
    DataPublicDataset,
    DataPublicDatasetRead,
    DataPublicDatasetCreate,
)

logger = get_logger(__name__)


router = APIRouter()


@router.post("", response_model=DataPublicDatasetRead)
async def datapublic_dataset_create(
    data: DataPublicDatasetCreate,
    session: Session = Depends(get_session),
) -> DataPublicDatasetRead:
    data = DataPublicDataset(**data.model_dump())

    with session.begin():
        session.add(data)

    session.refresh(data)

    return DataPublicDatasetRead(**data.model_dump())


@router.get("/{document_id}", response_model=DataPublicDatasetRead)
async def datapublic_dataset_read(
    document_id: UUID4 | UUID5,
    session: Session = Depends(get_session),
) -> DataPublicDatasetRead:
    statement = select(DataPublicDataset).where(DataPublicDataset.id == document_id)
    data = session.exec(statement).first()

    if not data:
        raise HTTPException(status_code=404, detail="Document not found")

    return DataPublicDatasetRead(**data.model_dump())


@router.post("/batch/import/json", response_model=SuccessResponse)
async def datapublic_dataset_batch_create(
    json_file: UploadFile,
    session: Session = Depends(get_session),
) -> SuccessResponse:
    try:
        data = json.load(json_file.file)

        with session.begin():
            for item in data:
                dataset = DataPublicDataset.model_validate(item)
                session.add(dataset)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SuccessResponse(message="Data imported successfully")


@router.get("/batch/export")
async def datapublic_dataset_batch_read(
    format: ExportFormat = ExportFormat.CSV,
    session: Session = Depends(get_session),
) -> FileResponse:
    statement = select(DataPublicDataset)
    dump = session.exec(statement).all()

    # re-encode data
    data = [DataPublicDatasetRead(**row.model_dump()) for row in dump]
    data = [json.loads(row.model_dump_json()) for row in data]

    with tempfile.NamedTemporaryFile(delete=False) as temp:
        if format == ExportFormat.CSV:
            df = pd.DataFrame(data)
            df.to_csv(temp.name, index=False)
            extension = "csv"
        elif format == ExportFormat.JSON:
            temp.write(json.dumps(data).encode("utf-8"))
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
