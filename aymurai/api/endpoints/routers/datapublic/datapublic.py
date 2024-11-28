import os
from threading import Lock

import torch
from fastapi import Body
from fastapi.routing import APIRouter

from aymurai.logger import get_logger
from aymurai.utils.misc import get_element
from aymurai.api.utils import load_pipeline
from aymurai.meta.api_interfaces import TextRequest, DocumentInformation
from aymurai.utils.cache import is_cached, cache_load, cache_save, get_cache_key

logger = get_logger(__name__)


torch.set_num_threads = 100  # FIXME: polemic ?
pipeline_lock = Lock()


router = APIRouter()


@router.post("/predict", response_model=DocumentInformation)
async def predict_over_text(
    request: TextRequest = Body({"text": "Buenos Aires, 17 de noviembre 2024"}),
) -> DocumentInformation:
    logger.info("datapublic predict single")

    # load datapublic pipeline
    pipeline = load_pipeline(
        os.path.join("resources", "pipelines", "production", "full-paragraph")
    )

    item = [{"path": "empty", "data": {"doc.text": request.text}}]
    item_id = get_cache_key(item, context="datapublic")

    if is_cached(item_id):
        prediction = cache_load(item_id)
        logger.info(f"cache loaded from key: {item_id}")
        logger.info(f"{prediction}")
        return DocumentInformation(**prediction)

    with pipeline_lock:
        processed = pipeline.preprocess(item)
        processed = pipeline.predict_single(processed[0])
        processed = pipeline.postprocess([processed])

    prediction = DocumentInformation(
        document=get_element(processed[0], ["data", "doc.text"]) or "",
        labels=get_element(processed[0], ["predictions", "entities"]) or [],
    )
    logger.info(f"saving in cache: {prediction}")
    cache_save(prediction.dict(), key=item_id)

    return prediction


@router.post("/document/validation", response_model=DocumentInformation)
async def document_validation(
    request: TextRequest = Body({"text": "Buenos Aires, 17 de noviembre 2024"}),
) -> DocumentInformation:
    pass
