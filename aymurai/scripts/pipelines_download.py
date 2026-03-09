import os

from aymurai.logger import get_logger
from aymurai.pipeline.pipeline import AymurAIPipeline
from aymurai.settings import settings

logger = get_logger(__name__)

RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH


def pipelines_download():
    logger.info("Loading pipelines and exit.")
    AymurAIPipeline.load(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "flair-anonymizer")
    )
    AymurAIPipeline.load(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "datapublic")
    )
