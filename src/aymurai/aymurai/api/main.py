import os
import time
import tempfile
from threading import Lock
from functools import lru_cache
from subprocess import getoutput

import torch
import cachetools
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from starlette.background import BackgroundTask
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi import Body, Depends, FastAPI, Request, UploadFile

from aymurai.logging import get_logger
from aymurai.utils.misc import get_element
from aymurai.pipeline import AymurAIPipeline
from aymurai.text.docx2html import docx2html
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER
from aymurai.utils.cache import is_cached, cache_load, cache_save, get_cache_key
from aymurai.meta.api_interfaces import Document, TextRequest, DocumentInformation

logger = get_logger(__name__)

MEMORY_CACHE_MAXSIZE = int(os.getenv("MEMORY_CACHE_MAXSIZE", 1))
MEMORY_CACHE_TTL = int(os.getenv("MEMORY_CACHE_TTL", 60))


mem_cache = cachetools.TTLCache(
    maxsize=MEMORY_CACHE_MAXSIZE,
    ttl=MEMORY_CACHE_MAXSIZE,
    getsizeof=lambda _: 0,
)

torch.set_num_threads = 100  # FIXME: polemic ?
pipeline_lock = Lock()


api = FastAPI(title="AymurAI API", version="0.5.0")

# configure CORS
CORS_ORIGINS_DEFAULT = [
    "http://localhost",
    "https://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    "0.0.0.0:8899",
    "0.0.0.0:3000",
]
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = CORS_ORIGINS.split(",")
origins = CORS_ORIGINS or CORS_ORIGINS_DEFAULT

api.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger.info("Loading server ...")


@lru_cache(maxsize=1)
def get_pipeline_doc_extract():
    return AymurAIPipeline.load("/resources/pipelines/production/doc-extraction")


@cachetools.cached(cache=mem_cache)
def load_pipeline(path: str):
    return AymurAIPipeline.load(path)


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
    StaticFiles(directory="/resources/api/static"),
    name="static",
)


def custom_openapi():
    if api.openapi_schema:
        return api.openapi_schema
    openapi_schema = get_openapi(
        title="AymurAI API - Swagger UI",
        version="0.5.0",
        description="",
        routes=api.routes,
    )
    openapi_schema["info"]["x-logo"] = {"url": "static/logo256-text.ico"}
    api.openapi_schema = openapi_schema
    return api.openapi_schema


api.openapi = custom_openapi


@api.post(
    "/datapublic/predict",
    response_model=DocumentInformation,
    tags=["datapublic"],
)
async def predict_over_text(
    request: TextRequest = Body({"text": " Buenos Aires, 17 de noviembre 2024"}),
) -> DocumentInformation:
    logger.info("datapublic predict single")

    # load datapublic pipeline
    pipeline = load_pipeline("/resources/pipelines/production/full-paragraph")

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


@api.post(
    "/anonymizer/predict",
    response_model=DocumentInformation,
    tags=["anonymizer"],
)
async def anonymizer_flair_predict(
    request: TextRequest = Body({"text": " Buenos Aires, 17 de noviembre 2024"}),
) -> DocumentInformation:
    logger.info("anonymization predict single")

    # load datapublic pipeline
    pipeline = load_pipeline("/resources/pipelines/production/flair-anonymizer")

    item = [{"path": "empty", "data": {"doc.text": request.text}}]
    item_id = get_cache_key(item, context="anonymizer")

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


@api.post(
    "/predict",  # FIXME: to be deprecated
    response_model=DocumentInformation,
    response_class=RedirectResponse,
    tags=["datapublic"],
    deprecated=True,
)
async def datapublic_predict(
    request: TextRequest = Body({"text": " Buenos Aires, 17 de noviembre 2024"}),
) -> DocumentInformation:
    url = api.url_path_for("/datapublic/predict")
    response = RedirectResponse(url=url)
    return response


# @api.post(
#     "/predict-batch",
#     response_model=list[DocumentInformation],
#     tags=["public_dataset"],
#     deprecated=True,
# )
# async def predict_over_text_batch(
#     request: list[TextRequest] = Body(
#         [
#             {"text": " Buenos Aires, 17 de noviembre 2024"},
#             {"text": " Hora de inicio: 11.00"},
#         ]
#     ),
#     pipeline: AymurAIPipeline = Depends(get_pipeline),
# ) -> DocumentInformation:
#     item = [{"path": "dummy", "data": {"doc.text": req.text}} for req in request]
#     logger.info(item)

#     with pipeline_lock:
#         processed = pipeline.preprocess(item)
#         processed = pipeline.predict(processed)
#         processed = pipeline.postprocess(processed)

#     logger.info(processed)

#     return [
#         DocumentInformation(
#             document=get_element(result, ["data", "doc.text"]) or "",
#             labels=get_element(result, ["predictions", "entities"]) or [],
#         )
#         for result in processed
#     ]


@api.post("/document-extract", response_model=DocumentInformation, tags=["documents"])
def plain_text_extractor(
    file: UploadFile,
    pipeline: AymurAIPipeline = Depends(get_pipeline_doc_extract),
) -> DocumentInformation:
    logger.info(f"receiving => {file.filename}")
    extension = MIMETYPE_EXTENSION_MAPPER.get(file.content_type)
    logger.info(f"detection extension: {extension} ({file.content_type})")

    # md5 = hashlib.md5(data).hexdigest()
    # tmp_filename = f"/tmp/{md5}.{extension}"
    candidate = next(tempfile._get_candidate_names())
    tmp_filename = f"/tmp/{candidate}.{extension}"
    logger.info(f"saving temp file on local storage => {tmp_filename}")
    with open(tmp_filename, "wb") as tmp_file:
        data = file.file.read()
        tmp_file.write(data)  # async write
    logger.info(f"saved temp file on local storage => {tmp_filename}")

    item = {
        "path": tmp_filename,
    }

    logger.info("processing data item")
    logger.info(f"{item}")
    with pipeline_lock:
        processed = pipeline.preprocess([item])

    logger.info(f"{processed}")

    logger.info(f"removing file => {tmp_filename}")
    os.remove(tmp_filename)
    return DocumentInformation(
        document=get_element(processed[0], ["data", "doc.text"], ""),
        labels=[],
    )


@api.post("/document-extract/docx2html", response_model=Document, tags=["documents"])
async def html_extractor(
    file: UploadFile,
) -> Document:
    logger.info(f"receiving => {file.filename}")

    with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".docx") as temp:
        # read file content
        binary_content = await file.read()
        temp.write(binary_content)
        temp.flush()

        content = docx2html(temp.name)

    return Document(**content)


@api.post("/docx-to-odt", tags=["documents"])
def doc2odt(file: UploadFile):
    with tempfile.NamedTemporaryFile(dir="/tmp", suffix=".docx") as temp:
        temp.write(file.file.read())
        temp.flush()
        cmd = "libreoffice --headless --convert-to odt --outdir /tmp {file}"
        getoutput(cmd.format(file=temp.name))
        odt = temp.name.replace(".docx", ".odt")

        return FileResponse(
            odt,
            background=BackgroundTask(os.remove, odt),
            media_type="application/octet-stream",
            filename=odt,
        )


if __name__ == "__main__":
    # download the necessary data
    logger.info("Loading pipelines and exit.")
    AymurAIPipeline.load("/resources/pipelines/production/doc-extraction")
    AymurAIPipeline.load("/resources/pipelines/production/flair-anonymizer")
    AymurAIPipeline.load("/resources/pipelines/production/full-paragraph")
