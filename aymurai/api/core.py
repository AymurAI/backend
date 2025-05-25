from fastapi.routing import APIRouter

from .endpoints.routers import anonymizer, database, datapublic, document, paragraph
from .endpoints.routers.server import stats

router = APIRouter()


# Server
router.include_router(stats.router, prefix="/server/stats", tags=["server"])

# Document
router.include_router(document.extract.router, prefix="/document", tags=["document"])
router.include_router(document.convert.router, prefix="/document", tags=["document"])
router.include_router(document.predict.router, tags=["document"])

# Paragraph
router.include_router(paragraph.predict.router, tags=["paragraph"])

# Datapublic
router.include_router(datapublic.validation.router, tags=["datapublic"])
router.include_router(datapublic.dataset.router, tags=["datapublic"])

# Anonymizer
router.include_router(anonymizer.compilation.router, tags=["anonymizer"])

# Database
router.include_router(database.dump.router, tags=["database"])
