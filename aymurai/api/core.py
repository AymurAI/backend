from fastapi.routing import APIRouter

from .endpoints.routers import document, paragraph
from .endpoints.routers.server import stats

# from .endpoints.routers.datapublic import datapublic


router = APIRouter()


# Server
router.include_router(stats.router, prefix="/server/stats", tags=["server"])

# Document
router.include_router(document.extract.router, prefix="/document", tags=["document"])
router.include_router(document.convert.router, prefix="/document", tags=["document"])
router.include_router(document.anonymizer.router, tags=["document"])

# Paragraph
router.include_router(paragraph.predict.router, tags=["paragraph"])
