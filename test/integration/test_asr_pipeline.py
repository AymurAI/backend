import json
import shutil

import pytest

from aymurai.meta.api_interfaces import (
    ASRDocument,
    DocumentAnnotations,
    DocumentInformation,
)
from aymurai.settings import settings


# MARK: ASR + Anonymizer
@pytest.mark.integration
@pytest.mark.slow
def test_should_anonymize_audio_document_when_running_real_asr_and_anonymizer_endpoints(
    integration_api_client,
    isolated_diskcache,
    integration_audio_bytes,
):
    if not settings.TRANSCRIBE_WS_URI:
        pytest.skip("TRANSCRIBE_WS_URI is required for real ASR integration test")

    if shutil.which(settings.LIBREOFFICE_BIN) is None:
        pytest.skip("LibreOffice binary is required for /anonymizer/anonymize-document")

    client = integration_api_client
    audio_bytes = integration_audio_bytes

    # --- Transcribe audio and persist in DB ---------------------------------
    transcribe_response = client.post(
        "/asr/transcribe?use_cache=false",
        files={"file": ("775.wav", audio_bytes, "audio/wav")},
    )
    assert transcribe_response.status_code == 200
    asr_document = ASRDocument.model_validate(transcribe_response.json())

    # --- Get predictions for each paragraph ---------------------------------
    paragraph_predictions: list[DocumentInformation] = []
    for paragraph in asr_document.document:
        predict_response = client.post(
            "/anonymizer/predict",
            json={"text": paragraph.text},
        )
        assert predict_response.status_code == 200
        paragraph_predictions.append(
            DocumentInformation.model_validate(predict_response.json())
        )

    # --- Compile anonymized document ----------------------------------------
    annotations = DocumentAnnotations(data=paragraph_predictions)
    compile_response = client.post(
        "/anonymizer/anonymize-document",
        data={
            "annotations": json.dumps(annotations.model_dump(mode="json")),
            "output_format": "audio",
        },
        files={"file": ("775.wav", audio_bytes, "audio/wav")},
    )

    assert compile_response.status_code == 200
    assert compile_response.headers["content-type"] == "application/octet-stream"
    assert len(compile_response.content) > 0
