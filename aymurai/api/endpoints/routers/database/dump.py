import os

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.routing import APIRouter

from aymurai.logger import get_logger
from aymurai.settings import settings

logger = get_logger(__name__)

router = APIRouter()


@router.get("/database/export")
async def database_dump() -> FileResponse:
    # Only support SQLite dumps for now
    db_uri = str(settings.SQLALCHEMY_DATABASE_URI)
    if not db_uri.startswith("sqlite:///"):
        raise HTTPException(
            status_code=400,
            detail="Database export only supported for SQLite",
        )

    db_file = db_uri.removeprefix("sqlite:///")
    if not os.path.exists(db_file):
        raise HTTPException(status_code=404, detail="Database file not found")

    # Return the raw SQLite file
    return FileResponse(
        path=db_file,
        filename="aymurai-backend.db",
        media_type="application/octet-stream",
    )
