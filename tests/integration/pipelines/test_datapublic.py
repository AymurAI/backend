import pytest

from aymurai.pipeline.pipeline import AymurAIPipeline


@pytest.mark.integration
@pytest.mark.slow
def test_should_load_pipeline_when_given_production_config(datapublic_pipeline):
    assert isinstance(datapublic_pipeline, AymurAIPipeline)
    assert hasattr(datapublic_pipeline, "pre_process")
    assert hasattr(datapublic_pipeline, "training_pipeline")
    assert hasattr(datapublic_pipeline, "post_process")


@pytest.mark.integration
@pytest.mark.slow
def test_should_preprocess_when_given_text_input(
    datapublic_pipeline, sample_text, build_pipeline_input
):
    input_item = build_pipeline_input(sample_text)
    result = datapublic_pipeline.preprocess([input_item])

    assert isinstance(result, list)
    assert len(result) > 0
    assert isinstance(result[0], dict)
    assert "data" in result[0]


@pytest.mark.integration
@pytest.mark.slow
def test_should_predict_single_when_given_preprocessed_item(
    datapublic_pipeline, sample_text, build_pipeline_input
):
    input_item = build_pipeline_input(sample_text)
    preprocessed = datapublic_pipeline.preprocess([input_item])
    result = datapublic_pipeline.predict_single(preprocessed[0])

    assert isinstance(result, dict)
    assert "predictions" in result
    assert result["predictions"] is not None


@pytest.mark.integration
@pytest.mark.slow
def test_should_postprocess_when_given_predicted_items(
    datapublic_pipeline, sample_text, build_pipeline_input
):
    input_item = build_pipeline_input(sample_text)
    preprocessed = datapublic_pipeline.preprocess([input_item])
    predicted = datapublic_pipeline.predict_single(preprocessed[0])
    result = datapublic_pipeline.postprocess([predicted])

    assert isinstance(result, list)
    assert len(result) > 0


@pytest.mark.integration
@pytest.mark.slow
def test_should_produce_entities_when_running_full_chain(
    datapublic_pipeline, sample_text, build_pipeline_input
):
    input_item = build_pipeline_input(sample_text)
    preprocessed = datapublic_pipeline.preprocess([input_item])
    predicted = datapublic_pipeline.predict_single(preprocessed[0])
    postprocessed = datapublic_pipeline.postprocess([predicted])

    result = postprocessed[0]
    assert "predictions" in result
    predictions = result["predictions"]
    assert predictions is not None and (
        isinstance(predictions, list) or isinstance(predictions, dict)
    )
