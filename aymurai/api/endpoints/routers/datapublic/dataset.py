import json
import os
import tempfile
from datetime import datetime
from enum import Enum

import pandas as pd
from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter
from sqlmodel import Session, select
from starlette.background import BackgroundTask

from aymurai.api.endpoints.meta.database import ExportFormat
from aymurai.database.schema import (
    Datapublic,
    DatapublicFormat,
    ModelType,
)
from aymurai.database.session import get_session
from aymurai.logger import get_logger

logger = get_logger(__name__)


# add a Dataset enum to include "all" and map NONE to "unsorted"
class Dataset(str, Enum):
    ALL = "all"
    UNSORTED = "unsorted"


router = APIRouter()


def get_records(
    session: Session,
    dataset: Dataset = Dataset.ALL,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    offset: int = 0,
    limit: int = 100,
) -> pd.DataFrame:
    # build base query
    statement = select(Datapublic)

    # filter by dataset/format
    if dataset != Dataset.ALL:
        if dataset == Dataset.UNSORTED:
            fmt = DatapublicFormat.NONE
        else:
            fmt = DatapublicFormat(dataset.value)
        statement = statement.where(Datapublic.validation_format == fmt)

    # optional date filters
    if start_date:
        statement = statement.where(Datapublic.created_at >= start_date)
    if end_date:
        statement = statement.where(Datapublic.created_at <= end_date)

    # pagination
    statement = statement.offset(offset).limit(limit)
    results = session.exec(statement).all()

    return pd.DataFrame([item.records for item in results])


@router.get(f"/pipeline/{ModelType.DATAPUBLIC}/records")
async def get_datapublic_records(
    dataset: Dataset = Dataset.ALL,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    offset: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> list[dict]:
    df = get_records(
        session=session,
        dataset=dataset,
        start_date=start_date,
        end_date=end_date,
        offset=offset,
        limit=limit,
    )

    encoded = df.to_json(orient="records", date_format="iso", index=False)

    return json.loads(encoded)


@router.get(f"/pipeline/{ModelType.DATAPUBLIC}/records/export")
async def database_export(
    dataset: Dataset = Dataset.ALL,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    offset: int = 0,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> FileResponse:
    data = get_records(
        session=session,
        dataset=dataset,
        start_date=start_date,
        end_date=end_date,
        offset=offset,
        limit=limit,
    )

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
        background=BackgroundTask(os.remove, temp.name),
        media_type="application/octet-stream",
    )
