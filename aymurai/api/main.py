import os
import time
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from aymurai.api import core
from aymurai.api.exceptions.handlers import register_exceptions_handlers
from aymurai.api.startup.database import check_db_connection
from aymurai.api.startup.marker import warm_marker_models
from aymurai.logger import get_logger
from aymurai.pipeline import AymurAIPipeline
from aymurai.settings import settings

try:
    from aymurai.version import __version__
except ImportError:
    __version__ = "0.0.0"

logger = get_logger(__name__)


RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("> Initializing service")
    logger.info(f">> Checking DB connection: `{settings.SQLALCHEMY_DATABASE_URI}`")
    try:
        check_db_connection()
        logger.info(">> Running Alembic migrations")
        alembic_cfg = Config(str(settings.ALEMBIC_INI_PATH))
        command.upgrade(alembic_cfg, "head")
    except Exception as error:
        logger.error("Error while starting up:", error)

    yield


api = FastAPI(
    title="AymurAI API",
    version=__version__,
    lifespan=lifespan,
)

register_exceptions_handlers(api)


# configure CORS
api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger.info("Loading server ...")
logger.info(f"CORS_ORIGINS: {settings.CORS_ORIGINS}")


@api.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@api.get("/", response_class=RedirectResponse, include_in_schema=False)
async def index():
    return "/docs"


# @api.get("/docs", include_in_schema=False)
# async def custom_swagger_ui_html():
#     return get_swagger_ui_html(
#         openapi_url=api.openapi_url,
#         title=f"{api.title} - Swagger UI",
#         swagger_css_url="https://cdn.jsdelivr.net/gh/danielperezrubio/swagger-dark-theme@main/assets/swagger-ui.min.css",
#     )


################################################################################
# MARK: API ENDPOINTS
################################################################################


# Healthcheck
@api.get("/server/healthcheck", status_code=200, tags=["server"])
def healthcheck():
    return {"status": "ok"}


# Api endpoints
api.include_router(core.router)


if __name__ == "__main__":
    # download the necessary data
    logger.info("Loading pipelines")
    AymurAIPipeline.load(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "flair-anonymizer")
    )
    AymurAIPipeline.load(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "full-paragraph")
    )
    warm_marker_models()
