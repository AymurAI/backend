from datetime import timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from sqlmodel import Session

from aymurai.api.meta.asr.coro import CoroSegment
from aymurai.database.meta.audio_transcription import AudioTranscription
from aymurai.database.utils import data_to_uuid
from aymurai.meta.api_interfaces import ASRDocument, ASRParagraph


# MARK: POST Transcribe
def test_should_transcribe_and_persist_document_when_service_returns_paragraphs(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes()
    document_id = data_to_uuid(audio_bytes)

    fake_segments = [
        CoroSegment(start=0.0, end=1.0, text="Hola mundo", speaker="1"),
    ]

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes",
        new=AsyncMock(return_value=fake_segments),
    ):
        response = client.post(
            "/asr/transcribe?use_cache=false",
            files={"file": ("sample.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    payload = ASRDocument.model_validate(response.json())
    assert str(payload.document_id) == str(document_id)
    assert len(payload.document) == 1
    assert payload.document[0].text == "Hola mundo"

    with Session(engine) as session:
        record = session.get(AudioTranscription, document_id)
        assert record is not None
        assert record.name == "sample.wav"
        first_item = cast(dict[str, Any], record.transcription[0])
        assert first_item["text"] == "Hola mundo"


# MARK: GET Validation
def test_should_return_validation_document_when_document_exists_in_database(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=220)
    document_id = data_to_uuid(audio_bytes)

    with Session(engine) as session:
        session.add(
            AudioTranscription(
                id=document_id,
                name="existing.wav",
                transcription=cast(
                    Any,
                    [
                        ASRParagraph(
                            speaker_no=1,
                            start=timedelta(seconds=0),
                            end=timedelta(seconds=1),
                            text="Texto original",
                        ).model_dump(mode="json")
                    ],
                ),
                validation=cast(
                    Any,
                    [
                        ASRParagraph(
                            speaker_no=1,
                            start=timedelta(seconds=0),
                            end=timedelta(seconds=1),
                            text="Texto validado",
                        ).model_dump(mode="json")
                    ],
                ),
            )
        )
        session.commit()

    response = client.get(f"/asr/validation/document/{document_id}")

    assert response.status_code == 200
    payload = ASRDocument.model_validate(response.json())
    assert str(payload.document_id) == str(document_id)
    assert payload.document[0].text == "Texto validado"


# MARK: POST Validation
def test_should_persist_validation_annotations_when_posting_validation_for_existing_document(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=330)
    document_id = data_to_uuid(audio_bytes)

    with Session(engine) as session:
        session.add(
            AudioTranscription(
                id=document_id,
                name="validation.wav",
                transcription=cast(
                    Any,
                    [
                        ASRParagraph(
                            speaker_no=1,
                            start=timedelta(seconds=0),
                            end=timedelta(seconds=1),
                            text="Linea base",
                        ).model_dump(mode="json")
                    ],
                ),
                validation=[],
            )
        )
        session.commit()

    body = [{"speaker_no": 1, "start": 0, "end": 1, "text": "Linea validada"}]
    response = client.post(f"/asr/validation/document/{document_id}", json=body)

    assert response.status_code == 200
    with Session(engine) as session:
        record = session.get(AudioTranscription, document_id)
        assert record is not None
        first_item = cast(dict[str, Any], record.validation[0])
        assert first_item["text"] == "Linea validada"


# MARK: POST Validation with speaker_name per paragraph
def test_should_persist_speaker_name_on_paragraph_when_posting_validation(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=440)
    document_id = data_to_uuid(audio_bytes)

    with Session(engine) as session:
        session.add(
            AudioTranscription(
                id=document_id,
                name="speakers.wav",
                transcription=cast(
                    Any,
                    [
                        ASRParagraph(
                            speaker_no=0,
                            start=timedelta(seconds=0),
                            end=timedelta(seconds=1),
                            text="Hola",
                        ).model_dump(mode="json")
                    ],
                ),
                validation=[],
            )
        )
        session.commit()

    body = [
        {
            "speaker_no": 0,
            "speaker_name": "Jueza",
            "start": 0,
            "end": 1,
            "text": "Hola validada",
        }
    ]
    response = client.post(f"/asr/validation/document/{document_id}", json=body)

    assert response.status_code == 200
    with Session(engine) as session:
        record = session.get(AudioTranscription, document_id)
        assert record is not None
        first_item = cast(dict[str, Any], record.validation[0])
        assert first_item["text"] == "Hola validada"
        assert first_item["speaker_name"] == "Jueza"


def test_should_store_null_speaker_name_when_not_provided(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=550)
    document_id = data_to_uuid(audio_bytes)

    with Session(engine) as session:
        session.add(
            AudioTranscription(
                id=document_id,
                name="preserve.wav",
                transcription=cast(
                    Any,
                    [
                        ASRParagraph(
                            speaker_no=0,
                            start=timedelta(seconds=0),
                            end=timedelta(seconds=1),
                            text="Base",
                        ).model_dump(mode="json")
                    ],
                ),
                validation=[],
            )
        )
        session.commit()

    body = [{"speaker_no": 0, "start": 0, "end": 1, "text": "Base validada"}]
    response = client.post(f"/asr/validation/document/{document_id}", json=body)

    assert response.status_code == 200
    with Session(engine) as session:
        record = session.get(AudioTranscription, document_id)
        assert record is not None
        first_item = cast(dict[str, Any], record.validation[0])
        assert first_item["speaker_name"] is None


# MARK: GET Validation with speaker_name per paragraph
def test_should_include_speaker_name_in_get_validation_response(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=770)
    document_id = data_to_uuid(audio_bytes)

    with Session(engine) as session:
        session.add(
            AudioTranscription(
                id=document_id,
                name="get_speakers.wav",
                transcription=cast(
                    Any,
                    [
                        ASRParagraph(
                            speaker_no=0,
                            speaker_name="Jueza",
                            start=timedelta(seconds=0),
                            end=timedelta(seconds=1),
                            text="Saludo",
                        ).model_dump(mode="json")
                    ],
                ),
                validation=[],
            )
        )
        session.commit()

    response = client.get(f"/asr/validation/document/{document_id}")

    assert response.status_code == 200
    payload = ASRDocument.model_validate(response.json())
    assert payload.document[0].speaker_name == "Jueza"


def test_should_return_null_speaker_name_when_none_stored(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=880)
    document_id = data_to_uuid(audio_bytes)

    with Session(engine) as session:
        session.add(
            AudioTranscription(
                id=document_id,
                name="empty_speakers.wav",
                transcription=cast(
                    Any,
                    [
                        ASRParagraph(
                            speaker_no=0,
                            start=timedelta(seconds=0),
                            end=timedelta(seconds=1),
                            text="x",
                        ).model_dump(mode="json")
                    ],
                ),
                validation=[],
            )
        )
        session.commit()

    response = client.get(f"/asr/validation/document/{document_id}")

    assert response.status_code == 200
    payload = ASRDocument.model_validate(response.json())
    assert payload.document[0].speaker_name is None
