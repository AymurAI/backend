import tempfile

import pandas as pd
from fastapi import Depends
from sqlmodel import Session, select
from fastapi.routing import APIRouter
from fastapi.responses import FileResponse

from aymurai.database.session import get_session
from aymurai.meta.api_interfaces import SuccessResponse
from aymurai.api.endpoints.meta.database import ExportFormat
from aymurai.database.schema import (
    DataPublicDataset,
    DataPublicDatasetRead,
    DataPublicDatasetCreate,
    DataPublicDatasetUpdate,
)

router = APIRouter()


@router.get("/export")
async def database_export(
    format: ExportFormat = ExportFormat.CSV,
    session: Session = Depends(get_session),
) -> FileResponse:
    statement = select(DataPublicDataset)
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

        return FileResponse(
            path=temp.name,
            filename=f"datapublic.{extension}",
            media_type="application/octet-stream",
        )


@router.post("/items/add", response_model=SuccessResponse)
async def item_add(
    data: DataPublicDatasetCreate,
    session: Session = Depends(get_session),
):
    item = DataPublicDataset.model_validate(data)

    session.add(item)
    session.commit()
    session.refresh(item)

    return SuccessResponse(id=item.id, msg="Item added")


@router.get("/items/{item_id}", response_model=DataPublicDatasetRead)
async def item_get(
    item_id: int,
    session: Session = Depends(get_session),
) -> DataPublicDatasetRead:
    statement = select(DataPublicDataset).where(DataPublicDataset.id == item_id)
    data = session.exec(statement).first()
    return data


@router.put("/items/{item_id}", response_model=DataPublicDatasetRead)
async def item_update(
    item_id: int,
    data: DataPublicDatasetUpdate,
    session: Session = Depends(get_session),
) -> DataPublicDatasetRead:
    statement = select(DataPublicDataset).where(DataPublicDataset.id == item_id)
    data_db = session.exec(statement).first()

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(data_db, field, value)

    session.add(data_db)
    session.commit()
    session.refresh(data_db)

    return data_db


@router.delete("/items/{item_id}", response_model=SuccessResponse)
async def item_delete(
    item_id: int,
    session: Session = Depends(get_session),
):
    statement = select(DataPublicDataset).where(DataPublicDataset.id == item_id)
    data = session.exec(statement).first()
    session.delete(data)
    session.commit()

    return SuccessResponse(id=item_id, msg="Item deleted")
