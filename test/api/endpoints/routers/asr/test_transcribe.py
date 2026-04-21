from datetime import timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, patch
from uuid import UUID

from sqlmodel import Session

from aymurai.api.meta.asr.websocket import (
    WLKMessageStatus,
    WLKMessageTranscriptionLine,
)
from aymurai.database.meta.audio_transcription import AudioTranscription
from aymurai.database.utils import data_to_uuid
from aymurai.meta.api_interfaces import ASRDocument, ASRParagraph

from aymurai.api.endpoints.routers.asr.transcribe import (
    _format_done_event,
    _format_error_event,
    _format_transcription_event,
)


# MARK: POST Transcribe
def test_should_transcribe_and_persist_document_when_service_returns_paragraphs(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes()
    document_id = data_to_uuid(audio_bytes)

    fake_status = WLKMessageStatus(
        status="active_transcription",
        lines=[
            WLKMessageTranscriptionLine(
                speaker=1,
                text="Hola mundo",
                start=timedelta(seconds=0),
                end=timedelta(seconds=1),
            )
        ],
        buffer_transcription="",
        buffer_diarization="",
        buffer_translation="",
        remaining_time_transcription=0.0,
        remaining_time_diarization=0.0,
        speaker_ids={},
    )

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes",
        new=AsyncMock(return_value=fake_status),
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

    annotations = [{"speaker_no": 1, "start": 0, "end": 1, "text": "Linea validada"}]
    response = client.post(f"/asr/validation/document/{document_id}", json=annotations)

    assert response.status_code == 200
    with Session(engine) as session:
        record = session.get(AudioTranscription, document_id)
        assert record is not None
        first_item = cast(dict[str, Any], record.validation[0])
        assert first_item["text"] == "Linea validada"


# MARK: SSE Formatters
def test_should_format_transcription_event_with_document_json():
    doc_id = UUID("00000000-0000-5000-8000-000000000000")
    paragraphs = [
        ASRParagraph(
            speaker_no=0,
            start=timedelta(seconds=0),
            end=timedelta(seconds=1),
            text="hola",
        )
    ]

    frame = _format_transcription_event(doc_id, paragraphs)

    assert frame.startswith("event: transcription\n")
    assert frame.endswith("\n\n")
    assert '"document_id"' in frame
    assert '"hola"' in frame


def test_should_format_done_event_with_document_json():
    doc_id = UUID("00000000-0000-5000-8000-000000000000")
    frame = _format_done_event(doc_id, [])

    assert frame.startswith("event: done\n")
    assert frame.endswith("\n\n")


def test_should_format_error_event_with_code_and_detail():
    frame = _format_error_event(detail="boom", code="UPSTREAM_SERVICE_ERROR")

    assert frame.startswith("event: error\n")
    assert '"code": "UPSTREAM_SERVICE_ERROR"' in frame
    assert '"detail": "boom"' in frame


# MARK: POST Transcribe Stream
def _parse_sse_events(body: str) -> list[tuple[str, str]]:
    """Parse SSE wire format into (event_name, data) tuples. Ignores comments."""
    events: list[tuple[str, str]] = []
    for chunk in body.split("\n\n"):
        chunk = chunk.strip()
        if not chunk or chunk.startswith(":"):
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in chunk.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        events.append((event_name, "\n".join(data_lines)))
    return events


def test_should_stream_transcription_events_and_persist_final_result(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes()
    document_id = data_to_uuid(audio_bytes)

    paragraph_snapshots = [
        [
            ASRParagraph(
                speaker_no=0,
                start=timedelta(seconds=0),
                end=timedelta(seconds=1),
                text="hola",
            )
        ],
        [
            ASRParagraph(
                speaker_no=0,
                start=timedelta(seconds=0),
                end=timedelta(seconds=2),
                text="hola mundo",
            )
        ],
    ]

    async def fake_generator(_payload):
        for snapshot in paragraph_snapshots:
            yield snapshot

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes_stream",
        new=fake_generator,
    ):
        response = client.post(
            "/asr/transcribe/stream?use_cache=false",
            files={"file": ("sample.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(response.text)
    names = [name for name, _ in events]
    assert names.count("transcription") == 2
    assert names[-1] == "done"

    done_payload = ASRDocument.model_validate_json(events[-1][1])
    assert str(done_payload.document_id) == str(document_id)
    assert done_payload.document[0].text == "hola mundo"

    # Final result persisted
    with Session(engine) as session:
        record = session.get(AudioTranscription, document_id)
        assert record is not None
        first_item = cast(dict[str, Any], record.transcription[0])
        assert first_item["text"] == "hola mundo"


def test_should_emit_only_done_event_when_stream_cache_hit(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=440)
    document_id = data_to_uuid(audio_bytes)

    # Seed DB
    with Session(engine) as session:
        session.add(
            AudioTranscription(
                id=document_id,
                name="cached.wav",
                transcription=cast(
                    Any,
                    [
                        ASRParagraph(
                            speaker_no=0,
                            start=timedelta(seconds=0),
                            end=timedelta(seconds=1),
                            text="cached text",
                        ).model_dump(mode="json")
                    ],
                ),
            )
        )
        session.commit()

    # Fail loud if the stream generator is called
    def _boom(_payload):
        raise AssertionError("should not call stream on cache hit")

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes_stream",
        side_effect=_boom,
    ):
        response = client.post(
            "/asr/transcribe/stream",
            files={"file": ("cached.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    names = [name for name, _ in events]
    assert names == ["done"]

    payload = ASRDocument.model_validate_json(events[0][1])
    assert payload.document[0].text == "cached text"
