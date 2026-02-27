import uuid

from sqlmodel import Session

from aymurai.database.schema import AudioTranscription
from aymurai.meta.api_interfaces import ASRParagraph


def audio_transcription_get(
    transcription_id: uuid.UUID,
    session: Session,
) -> AudioTranscription | None:
    return session.get(AudioTranscription, transcription_id)


def audio_transcription_create_or_update(
    transcription_id: uuid.UUID,
    name: str,
    transcription: list[ASRParagraph],
    session: Session,
) -> AudioTranscription:
    record = session.get(AudioTranscription, transcription_id)
    serialized_transcription = [
        paragraph.model_dump(mode="json") for paragraph in transcription
    ]

    if not record:
        record = AudioTranscription(
            id=transcription_id,
            name=name,
            transcription=serialized_transcription,
            validation=[],
        )
    else:
        record.name = name
        record.transcription = serialized_transcription
        record.validation = []

    session.add(record)
    session.commit()
    session.refresh(record)
    return record
