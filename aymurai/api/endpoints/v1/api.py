from fastapi.routing import APIRouter

from .routers import database

router = APIRouter()

router.include_router(database.router, prefix="/database")
