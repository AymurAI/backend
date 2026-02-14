from typing import Any

import pytest

from aymurai.pipeline.pipeline import AymurAIPipeline


@pytest.fixture
def input_item(sample_text: str, build_pipeline_input) -> dict[str, Any]:
    return build_pipeline_input(sample_text)


@pytest.fixture
def preprocessed_item(
    datapublic_pipeline,
    input_item: dict[str, Any],
) -> dict[str, Any]:
    return datapublic_pipeline.preprocess([input_item])[0]


@pytest.fixture
def predicted_item(
    datapublic_pipeline,
    preprocessed_item: dict[str, Any],
) -> dict[str, Any]:
    return datapublic_pipeline.predict_single(preprocessed_item)


@pytest.fixture
def postprocessed_item(
    datapublic_pipeline,
    predicted_item: dict[str, Any],
) -> dict[str, Any]:
    return datapublic_pipeline.postprocess([predicted_item])[0]


@pytest.mark.integration
@pytest.mark.slow
def test_should_load_pipeline_when_given_production_config(datapublic_pipeline):
    assert isinstance(datapublic_pipeline, AymurAIPipeline)
    assert hasattr(datapublic_pipeline, "pre_process")
    assert hasattr(datapublic_pipeline, "training_pipeline")
    assert hasattr(datapublic_pipeline, "post_process")


@pytest.mark.integration
@pytest.mark.slow
def test_should_preprocess_when_given_text_input(preprocessed_item: dict[str, Any]):
    assert isinstance(preprocessed_item, dict)
    assert "data" in preprocessed_item


@pytest.mark.integration
@pytest.mark.slow
def test_should_predict_single_when_given_preprocessed_item(
    predicted_item: dict[str, Any],
):
    assert isinstance(predicted_item, dict)
    assert "predictions" in predicted_item
    assert predicted_item["predictions"] is not None


@pytest.mark.integration
@pytest.mark.slow
def test_should_postprocess_when_given_predicted_items(
    postprocessed_item: dict[str, Any],
):
    assert isinstance(postprocessed_item, dict)


@pytest.mark.integration
@pytest.mark.slow
def test_should_produce_entities_when_running_full_chain(
    postprocessed_item: dict[str, Any],
):
    result = postprocessed_item
    assert "predictions" in result
    predictions = result["predictions"]
    assert predictions is not None and (
        isinstance(predictions, list) or isinstance(predictions, dict)
    )
