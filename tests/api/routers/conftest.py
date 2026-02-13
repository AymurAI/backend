from unittest.mock import MagicMock

from tests.conftest import (
    build_label,
    build_anonymization_paragraph,
    build_datapublic_paragraph,
)


def build_mock_pipeline():
    mock = MagicMock()

    mock.preprocess.side_effect = lambda item: item

    def predict_single_impl(item):
        item["predictions"] = {"entities": [build_label()]}
        return item

    mock.predict_single.side_effect = predict_single_impl

    mock.postprocess.side_effect = lambda items: items

    return mock


def build_processed_data_item(text: str = "sample", labels: list | None = None):
    return {
        "path": "empty",
        "data": {"doc.text": text},
        "predictions": {"entities": labels or []},
    }
