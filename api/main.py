import os
import time
import tempfile
from threading import Lock
from functools import lru_cache

import torch
from fastapi.testclient import TestClient
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body, Depends, FastAPI, Request, UploadFile

from aymurai.logging import get_logger
from aymurai.utils.misc import get_element
from aymurai.pipeline import AymurAIPipeline
from aymurai.text.extraction import MIMETYPE_EXTENSION_MAPPER
from aymurai.meta.api_interfaces import TextRequest, DocumentInformation

logger = get_logger(__name__)

torch.set_num_threads = 100
pipeline_lock = Lock()


api = FastAPI()

# configure CORS
origins = [
    "http://localhost",
    "https://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    "0.0.0.0:8899",
    "0.0.0.0:3000",
]

api.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger.info("Loading server ...")


@lru_cache(maxsize=1)
def get_pipeline():
    return AymurAIPipeline.load("/resources/pipelines/production/full-paragraph")


@lru_cache(maxsize=1)
def get_pipeline_doc_extract():
    return AymurAIPipeline.load("/resources/pipelines/production/doc-extraction")


@api.on_event("startup")
async def load_pipelines():
    get_pipeline()
    get_pipeline_doc_extract()


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


@api.post("/predict", response_model=DocumentInformation)
async def predict_over_text(
    request: TextRequest = Body({"text": " Buenos Aires, 17 de noviembre 2024"}),
    pipeline: AymurAIPipeline = Depends(get_pipeline),
) -> DocumentInformation:
    logger.info("predict single")
    item = [{"path": "dummy", "data": {"doc.text": request.text}}]

    with pipeline_lock:
        processed = pipeline.preprocess(item)
        processed = pipeline.predict_single(processed[0])
        processed = pipeline.postprocess([processed])

    logger.info(processed)

    return DocumentInformation(
        document=get_element(processed[0], ["data", "doc.text"]) or "",
        labels=get_element(processed[0], ["predictions", "entities"]) or [],
    )


@api.post("/predict-batch", response_model=list[DocumentInformation])
async def predict_over_text_batch(
    request: list[TextRequest] = Body(
        [
            {"text": " Buenos Aires, 17 de noviembre 2024"},
            {"text": " Hora de inicio: 11.00"},
        ]
    ),
    pipeline: AymurAIPipeline = Depends(get_pipeline),
) -> DocumentInformation:

    item = [{"path": "dummy", "data": {"doc.text": req.text}} for req in request]
    logger.info(item)

    with pipeline_lock:
        processed = pipeline.preprocess(item)
        processed = pipeline.predict(processed)
        processed = pipeline.postprocess(processed)

    logger.info(processed)

    return [
        DocumentInformation(
            document=get_element(result, ["data", "doc.text"]) or "",
            labels=get_element(result, ["predictions", "entities"]) or [],
        )
        for result in processed
    ]


@api.post("/document-extract", response_model=DocumentInformation)
def create_upload_file(
    file: UploadFile,
    pipeline: AymurAIPipeline = Depends(get_pipeline_doc_extract),
) -> DocumentInformation:
    logger.info(f"reciving => {file.filename}")
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


client = TestClient(api)


def test_read_main():
    input_ = {"text": " Buenos Aires, 21 de febrero de 2017"}
    output_ = {
        "document": " Buenos Aires, 21 de febrero de 2017",
        "labels": [
            {
                "text": "21 de febrero de 2017",
                "start_char": 15,
                "end_char": 36,
                "attrs": {
                    "aymurai_label": "FECHA_RESOLUCION",
                    "aymurai_label_subclass": None,
                    "aymurai_alt_text": None,
                },
            }
        ],
    }

    response = client.post("/predict", json=input_)
    assert response.status_code == 200
    assert response.json() == output_


if __name__ == "__main__":
    logger.info("Loading pipelines and exit.")
    get_pipeline()
    get_pipeline_doc_extract()
