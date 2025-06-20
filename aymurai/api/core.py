from fastapi.routing import APIRouter

from .endpoints.routers.anonymizer import anonymizer
from .endpoints.routers.anonymizer import database as anonymizer_database
from .endpoints.routers.datapublic import datapublic

from .endpoints.routers.misc import convert, document_extract
from .endpoints.routers.server import stats

router = APIRouter()


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
# router.include_router(
#     anonymizer_database.router,
#     prefix="/anonymizer/database",
#     tags=["anonymization/database"],
# )

# Datapublic
router.include_router(
    datapublic.router,
    prefix="/datapublic",
    tags=["datapublic/model"],
)


# Misc
router.include_router(document_extract.router, tags=["document"], deprecated=True)
router.include_router(document_extract.router, prefix="/misc", tags=["document"])

# Document conversion
router.include_router(convert.router, tags=["Document conversion"])
