import os
from functools import lru_cache

import cachetools

from aymurai.logger import get_logger
from aymurai.settings import settings
from aymurai.pipeline import AymurAIPipeline

logger = get_logger(__name__)


mem_cache = cachetools.TTLCache(
    maxsize=settings.MEMORY_CACHE_MAXSIZE,
    ttl=settings.MEMORY_CACHE_MAXSIZE,
    getsizeof=lambda _: 0,
)

RESOURCES_BASEPATH = settings.RESOURCES_BASEPATH


@cachetools.cached(cache=mem_cache)
def load_pipeline(path: str):
    return AymurAIPipeline.load(path)


@lru_cache(maxsize=1)
def get_pipeline_doc_extract():
    return AymurAIPipeline.load(
        os.path.join(RESOURCES_BASEPATH, "pipelines", "production", "doc-extraction")
    )
