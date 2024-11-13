from fastapi.routing import APIRouter

from .routers import anonymizer
from .routers.database import datapublic, anonymization

router = APIRouter()

router.include_router(datapublic.router, prefix="/database/datapublic")
router.include_router(anonymization.router, prefix="/database/anonymization")

router.include_router(anonymizer.router, prefix="/anonymizer")
