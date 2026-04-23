import json
from datetime import timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, patch
from uuid import UUID

from sqlmodel import Session

from aymurai.api.endpoints.routers.asr.transcribe import (
    _format_error_event,
    _format_sse_event,
)
from aymurai.api.meta.asr.websocket import (
    WLKMessageStatus,
    WLKMessageTranscriptionLine,
)
from aymurai.audio.asr_client import ASRStreamChunk
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


def test_should_exclude_empty_text_paragraphs_from_transcribe_response(
    asr_test_client,
    make_wav_bytes,
):
    client, _ = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=110)

    fake_status = WLKMessageStatus(
        status="active_transcription",
        lines=[
            WLKMessageTranscriptionLine(
                speaker=1,
                text="Hola",
                start=timedelta(seconds=0),
                end=timedelta(seconds=1),
            ),
            WLKMessageTranscriptionLine(
                speaker=1,
                text="   ",
                start=timedelta(seconds=1),
                end=timedelta(seconds=2),
            ),
            WLKMessageTranscriptionLine(
                speaker=2,
                text="",
                start=timedelta(seconds=2),
                end=timedelta(seconds=3),
            ),
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
    assert len(payload.document) == 1
    assert payload.document[0].text == "Hola"


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

    frame = _format_sse_event("transcription", doc_id, paragraphs)

    assert frame.startswith("event: transcription\n")
    assert frame.endswith("\n\n")
    assert '"document_id"' in frame
    assert '"hola"' in frame


def test_should_format_done_event_with_document_json():
    doc_id = UUID("00000000-0000-5000-8000-000000000000")
    frame = _format_sse_event("done", doc_id, [])

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
            yield ASRStreamChunk(
                paragraphs=snapshot,
                current_time=snapshot[-1].end.total_seconds(),
                total_time=2.0,
            )

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


def test_should_mark_transcribe_endpoint_as_deprecated_in_openapi(
    asr_test_client,
):
    client, _ = asr_test_client
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    transcribe_op = schema["paths"]["/asr/transcribe"]["post"]
    assert transcribe_op.get("deprecated") is True

    stream_op = schema["paths"]["/asr/transcribe/stream"]["post"]
    assert stream_op.get("deprecated") is not True


def test_should_emit_error_event_when_upstream_fails_mid_stream(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=550)
    document_id = data_to_uuid(audio_bytes)

    async def failing_generator(_payload):
        yield ASRStreamChunk(
            paragraphs=[
                ASRParagraph(
                    speaker_no=0,
                    start=timedelta(seconds=0),
                    end=timedelta(seconds=1),
                    text="partial",
                )
            ],
            current_time=1.0,
            total_time=2.0,
        )
        raise RuntimeError("Transcription service websocket error")

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes_stream",
        new=failing_generator,
    ):
        response = client.post(
            "/asr/transcribe/stream?use_cache=false",
            files={"file": ("err.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    names = [name for name, _ in events]
    assert "error" in names
    assert names[-1] == "error"

    error_payload = json.loads(events[-1][1])
    assert error_payload["code"] == "UPSTREAM_SERVICE_ERROR"

    # No DB record should be written
    with Session(engine) as session:
        record = session.get(AudioTranscription, document_id)
        assert record is None


def test_should_emit_internal_error_event_when_generator_raises_unexpected_exception(
    asr_test_client,
    make_wav_bytes,
):
    client, _ = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=660)

    async def broken_generator(_payload):
        yield ASRStreamChunk(
            paragraphs=[
                ASRParagraph(
                    speaker_no=0,
                    start=timedelta(seconds=0),
                    end=timedelta(seconds=1),
                    text="partial",
                )
            ],
            current_time=1.0,
            total_time=2.0,
        )
        raise ValueError("something unexpected")

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes_stream",
        new=broken_generator,
    ):
        response = client.post(
            "/asr/transcribe/stream?use_cache=false",
            files={"file": ("broken.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    names = [name for name, _ in events]
    assert "error" in names
    assert names[-1] == "error"

    error_payload = json.loads(events[-1][1])
    assert error_payload["code"] == "INTERNAL_ERROR"


def test_should_include_progress_fields_in_done_event(
    asr_test_client,
    make_wav_bytes,
):
    client, _ = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=770)

    async def fake_generator(_payload):
        yield ASRStreamChunk(
            paragraphs=[
                ASRParagraph(
                    speaker_no=0,
                    start=timedelta(seconds=0),
                    end=timedelta(seconds=5),
                    text="hello",
                )
            ],
            current_time=5.0,
            total_time=10.0,
        )

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes_stream",
        new=fake_generator,
    ):
        response = client.post(
            "/asr/transcribe/stream?use_cache=false",
            files={"file": ("progress.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    done_payload = ASRDocument.model_validate_json(events[-1][1])
    assert done_payload.current_time == 5.0
    assert done_payload.total_time == 10.0


def test_should_emit_keepalive_comments_during_long_transcription(
    asr_test_client,
    make_wav_bytes,
):
    client, _ = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=880)

    async def slow_generator(_payload):
        import asyncio

        yield ASRStreamChunk(
            paragraphs=[
                ASRParagraph(
                    speaker_no=0,
                    start=timedelta(seconds=0),
                    end=timedelta(seconds=1),
                    text="first",
                )
            ],
            current_time=1.0,
            total_time=2.0,
        )
        await asyncio.sleep(0.3)
        yield ASRStreamChunk(
            paragraphs=[
                ASRParagraph(
                    speaker_no=0,
                    start=timedelta(seconds=0),
                    end=timedelta(seconds=2),
                    text="first second",
                )
            ],
            current_time=2.0,
            total_time=2.0,
        )

    with (
        patch(
            "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes_stream",
            new=slow_generator,
        ),
        patch(
            "aymurai.api.endpoints.routers.asr.transcribe.settings.TRANSCRIBE_SSE_KEEPALIVE_SECONDS",
            0,
        ),
    ):
        response = client.post(
            "/asr/transcribe/stream?use_cache=false",
            files={"file": ("keepalive.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    assert ": keepalive" in response.text or "event: done" in response.text


def test_should_return_upstream_error_when_transcribe_audio_bytes_raises_websocket_runtime_error(
    asr_test_client,
    make_wav_bytes,
):
    client, _ = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=990)

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes",
        new=AsyncMock(
            side_effect=RuntimeError("Transcription service websocket error")
        ),
    ):
        response = client.post(
            "/asr/transcribe?use_cache=false",
            files={"file": ("ws_err.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 502


def test_should_return_api_error_when_transcribe_audio_bytes_returns_none(
    asr_test_client,
    make_wav_bytes,
):
    client, _ = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=1100)

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.transcribe_audio_bytes",
        new=AsyncMock(return_value=None),
    ):
        response = client.post(
            "/asr/transcribe?use_cache=false",
            files={"file": ("no_result.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 500


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
