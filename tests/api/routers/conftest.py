from unittest.mock import MagicMock

from tests.api.conftest import build_label


def build_mock_pipeline():
    mock = MagicMock()

    mock.preprocess.side_effect = lambda item: item

    def predict_single_impl(item):
        item["predictions"] = {"entities": [build_label().model_dump(mode="json")]}
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
