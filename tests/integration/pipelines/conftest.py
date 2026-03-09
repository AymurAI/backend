import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from aymurai.pipeline.pipeline import AymurAIPipeline

os.environ.setdefault("DISKCACHE_ROOT", "resources/cache/diskcache")
os.environ.setdefault("AYMURAI_CACHE_BASEPATH", "resources/cache/aymurai")


PIPELINE_CONFIGS = {
    "anonymizer": "resources/pipelines/production/flair-anonymizer",
    "datapublic": "resources/pipelines/production/datapublic",
}


def load_test_pipeline(name: str) -> "AymurAIPipeline":
    from aymurai.pipeline.pipeline import AymurAIPipeline

    if name not in PIPELINE_CONFIGS:
        raise ValueError(
            f"Unknown pipeline: {name}. Available: {list(PIPELINE_CONFIGS.keys())}"
        )

    path = PIPELINE_CONFIGS[name]
    return AymurAIPipeline.load(path, print_config=False)


@pytest.fixture(scope="session")
def anonymizer_pipeline() -> "AymurAIPipeline":
    return load_test_pipeline("anonymizer")


@pytest.fixture(scope="session")
def datapublic_pipeline() -> "AymurAIPipeline":
    return load_test_pipeline("datapublic")


@pytest.fixture
def sample_text() -> str:
    return (
        "El día 15 de marzo de 2023, el Sr. Juan Pérez fue imputado por el delito de "
        "lesiones graves. La víctima, María González, declaró en el Juzgado Civil de Buenos Aires."
    )


def _build_pipeline_input(text: str) -> dict[str, Any]:
    return {
        "path": "test",
        "extension": "",
        "dataset": "",
        "data": {"doc.text": text},
        "annotations": None,
        "predictions": {},
    }


@pytest.fixture
def build_pipeline_input() -> Callable[[str], dict[str, Any]]:
    return _build_pipeline_input
