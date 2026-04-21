import uuid

from sqlmodel import Session

from aymurai.database.schema import AudioTranscription
from aymurai.meta.api_interfaces import ASRParagraph


def audio_transcription_get(
    transcription_id: uuid.UUID,
    session: Session,
) -> AudioTranscription | None:
    """
    Get audio transcription record by ID.

    Args:
        transcription_id (uuid.UUID): ID of the transcription record.
        session (Session): SQLAlchemy session.

    Returns:
        AudioTranscription | None: AudioTranscription record if found, else None.
    """
    return session.get(AudioTranscription, transcription_id)


def audio_transcription_create_or_update(
    transcription_id: uuid.UUID,
    name: str,
    transcription: list[ASRParagraph],
    session: Session,
    speaker_names: dict[str, str] | None = None,
) -> AudioTranscription:
    """
    Create or update an audio transcription record.

    Args:
        transcription_id (uuid.UUID): ID of the transcription record.
        name (str): Name of the transcription.
        transcription (list[ASRParagraph]): List of ASRParagraph objects representing the transcription.
        session (Session): SQLAlchemy session.
        speaker_names (dict[str, str] | None, optional): Mapping of speaker index (as str) to user-provided name.
            When None, the existing value is preserved on updates (defaults to empty dict on create).
            When provided (including an empty dict), replaces the stored value.

    Returns:
        AudioTranscription: The created or updated AudioTranscription record.
    """
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
            speaker_names=speaker_names if speaker_names is not None else {},
        )
    else:
        record.name = name
        record.transcription = serialized_transcription
        record.validation = []
        if speaker_names is not None:
            record.speaker_names = speaker_names

    session.add(record)
    session.commit()
    session.refresh(record)
    return record
