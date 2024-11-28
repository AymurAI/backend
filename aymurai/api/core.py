from fastapi.routing import APIRouter

from .endpoints.routers.server import stats
from .endpoints.routers.misc import document_extract
from .endpoints.routers.anonymizer import database as anonymizer_database, anonymizer
from .endpoints.routers.datapublic import database as datapublic_database, datapublic

# from .endpoints.routers.database import datapublic, anonymization

router = APIRouter()

# router.include_router(datapublic.router, prefix="/database/datapublic")
# router.include_router(anonymization.router, prefix="/database/anonymization")

# Server
router.include_router(
    stats.router,
    prefix="/server/stats",
    tags=["server"],
)

# Anonymizer
router.include_router(
    anonymizer.router,
    prefix="/anonymizer",
    tags=["anonymization/model"],
)
router.include_router(
    anonymizer_database.router,
    prefix="/anonymizer/database",
    tags=["anonymization/database"],
)

# Datapublic
router.include_router(
    datapublic.router,
    prefix="/datapublic",
    tags=["/datapublic/model"],
)
router.include_router(
    datapublic_database.router,
    prefix="/datapublic/database",
    tags=["/datapublic/database"],
)

# Misc
router.include_router(document_extract.router, tags=["document"], deprecated=True)
router.include_router(document_extract.router, prefix="/misc", tags=["document"])
