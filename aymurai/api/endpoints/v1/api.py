from fastapi.routing import APIRouter

from .routers import datapublic, anonymization

router = APIRouter()

router.include_router(datapublic.router, prefix="/datapublic")
router.include_router(anonymization.router, prefix="/anonymization")
