import json
from datetime import timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from sqlmodel import Session

from aymurai.api.endpoints.routers.asr.transcribe import _estimate_progress
from aymurai.api.meta.asr.coro import CoroSegment, CoroStreamDelta, CoroStreamSegments
from aymurai.database.meta.audio_transcription import AudioTranscription
from aymurai.database.utils import data_to_uuid
from aymurai.meta.api_interfaces import ASRDocument, ASRParagraph


def _parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block.startswith("data:"):
            continue
        events.append(json.loads(block[len("data:") :].strip()))
    return events


def _fake_stream(events):
    async def _gen(*args, **kwargs):
        for event in events:
            yield event

    return _gen


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


# MARK: progress estimation
def test_progress_should_be_zero_for_no_characters():
    assert _estimate_progress(0, 10.0) == 0.0


def test_progress_should_be_about_ninety_percent_at_estimated_completion():
    # raw == 1.0 when chars == duration * 17
    progress = _estimate_progress(170, 10.0)
    assert progress is not None
    assert abs(progress - 0.9) < 1e-6


def test_progress_should_stay_below_one_even_when_estimate_exceeded():
    progress = _estimate_progress(100_000, 1.0)
    assert progress is not None
    assert progress < 1.0


def test_progress_should_be_monotonic_non_decreasing():
    values = [_estimate_progress(chars, 10.0) for chars in range(0, 500, 25)]
    assert all(a is not None and b is not None for a, b in zip(values, values[1:]))
    assert all(a <= b for a, b in zip(values, values[1:]))  # type: ignore[operator]


def test_progress_should_be_none_when_duration_unavailable():
    assert _estimate_progress(100, None) is None


def test_progress_should_be_none_when_duration_non_positive():
    assert _estimate_progress(100, 0.0) is None


# MARK: POST Transcribe stream
def test_stream_should_emit_meta_deltas_segments_done_and_persist(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(duration_seconds=2.0)
    document_id = data_to_uuid(audio_bytes)

    events = [
        CoroStreamDelta(text="Hola "),
        CoroStreamDelta(text="mundo"),
        CoroStreamSegments(
            segments=[CoroSegment(start=0.0, end=1.0, text="Hola mundo", speaker="1")]
        ),
    ]

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.stream_transcribe_audio_bytes",
        new=_fake_stream(events),
    ):
        response = client.post(
            "/asr/transcribe/stream?use_cache=false",
            files={"file": ("sample.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    parsed = _parse_sse(response.text)

    types = [event["type"] for event in parsed]
    assert types == ["meta", "delta", "delta", "segments", "done"]

    meta = parsed[0]
    assert meta["document_id"] == str(document_id)
    assert meta["duration"] is not None and abs(meta["duration"] - 2.0) < 0.1

    deltas = [event for event in parsed if event["type"] == "delta"]
    assert deltas[0]["text"] == "Hola "
    assert deltas[1]["text"] == "mundo"
    progresses = [event["progress"] for event in deltas]
    assert all(0.0 <= p < 1.0 for p in progresses)
    assert progresses == sorted(progresses)

    segments_event = next(event for event in parsed if event["type"] == "segments")
    assert segments_event["document"][0]["text"] == "Hola mundo"

    assert parsed[-1] == {"type": "done", "progress": 1.0}

    with Session(engine) as session:
        record = session.get(AudioTranscription, document_id)
        assert record is not None
        first_item = cast(dict[str, Any], record.transcription[0])
        assert first_item["text"] == "Hola mundo"


def test_stream_should_emit_cached_document_without_calling_coro(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=210)
    document_id = data_to_uuid(audio_bytes)

    with Session(engine) as session:
        session.add(
            AudioTranscription(
                id=document_id,
                name="cached.wav",
                transcription=cast(
                    Any,
                    [
                        ASRParagraph(
                            speaker_no=1,
                            start=timedelta(seconds=0),
                            end=timedelta(seconds=1),
                            text="Texto cacheado",
                        ).model_dump(mode="json")
                    ],
                ),
                validation=[],
            )
        )
        session.commit()

    def _fail(*args, **kwargs):
        raise AssertionError("coro must not be called on cache hit")

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.stream_transcribe_audio_bytes",
        new=_fail,
    ):
        response = client.post(
            "/asr/transcribe/stream",
            files={"file": ("cached.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    parsed = _parse_sse(response.text)
    types = [event["type"] for event in parsed]
    assert types == ["meta", "segments", "done"]
    segments_event = next(event for event in parsed if event["type"] == "segments")
    assert segments_event["document"][0]["text"] == "Texto cacheado"


def test_stream_should_emit_error_event_on_upstream_failure(
    asr_test_client,
    make_wav_bytes,
):
    client, engine = asr_test_client
    audio_bytes = make_wav_bytes(freq_hz=190)
    document_id = data_to_uuid(audio_bytes)

    def _raising_stream(*args, **kwargs):
        async def _gen():
            raise RuntimeError("Transcription service error")
            yield  # pragma: no cover

        return _gen()

    with patch(
        "aymurai.api.endpoints.routers.asr.transcribe.stream_transcribe_audio_bytes",
        new=_raising_stream,
    ):
        response = client.post(
            "/asr/transcribe/stream?use_cache=false",
            files={"file": ("err.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    parsed = _parse_sse(response.text)
    types = [event["type"] for event in parsed]
    assert "error" in types
    assert "done" not in types
    error_event = next(event for event in parsed if event["type"] == "error")
    assert "Transcription service error" in error_event["detail"]

    with Session(engine) as session:
        assert session.get(AudioTranscription, document_id) is None


def test_stream_should_omit_progress_when_duration_unavailable(
    asr_test_client,
    make_wav_bytes,
):
    client, _ = asr_test_client
    audio_bytes = make_wav_bytes()

    events = [
        CoroStreamDelta(text="Hola"),
        CoroStreamSegments(
            segments=[CoroSegment(start=0.0, end=1.0, text="Hola", speaker="1")]
        ),
    ]

    with (
        patch(
            "aymurai.api.endpoints.routers.asr.transcribe.stream_transcribe_audio_bytes",
            new=_fake_stream(events),
        ),
        patch(
            "aymurai.api.endpoints.routers.asr.transcribe.probe_audio_duration",
            return_value=None,
        ),
    ):
        response = client.post(
            "/asr/transcribe/stream?use_cache=false",
            files={"file": ("sample.wav", audio_bytes, "audio/wav")},
        )

    assert response.status_code == 200
    parsed = _parse_sse(response.text)
    meta = parsed[0]
    assert meta["duration"] is None
    delta = next(event for event in parsed if event["type"] == "delta")
    assert "progress" not in delta
