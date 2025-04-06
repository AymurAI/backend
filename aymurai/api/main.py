import os
import time
from contextlib import asynccontextmanager

import torch
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from aymurai.api import core
from aymurai.logger import get_logger
from aymurai.settings import settings
from aymurai.pipeline import AymurAIPipeline
from aymurai.api.startup.database import check_db_connection


logger = get_logger(__name__)


torch.set_num_threads = 100  # FIXME: polemic ?

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
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# configure CORS
api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger.info(f"Loading server (Aymurai API - {settings.APP_VERSION})...")
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


api.mount(
    "/static",
    StaticFiles(directory=os.path.join(RESOURCES_BASEPATH, "api", "static")),
    name="static",
)


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
    logger.info("Loading pipelines and exit.")
    AymurAIPipeline.load(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "doc-extraction")
    )
    AymurAIPipeline.load(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "flair-anonymizer")
    )
    AymurAIPipeline.load(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "full-paragraph")
    )
