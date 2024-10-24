from fastapi.routing import APIRouter

from aymurai.api.endpoints.v1.meta.database import ExportFormat

router = APIRouter()


@router.get("/export")
async def database_export(format: ExportFormat = ExportFormat.CSV):
    pass


@router.post("/items/")
async def item_add():
    pass


@router.get("/items/{item_id}")
async def item_get(item_id: str):
    pass


@router.delete("/items/{item_id}")
async def item_delete(item_id: str):
    pass
