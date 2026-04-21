import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, func, text
from sqlmodel import Field, SQLModel

# FIXME: Not proper resposibility of the database layer to import ASRParagraph,
# the direction of dependency should be inverted.
from aymurai.meta.api_interfaces import ASRParagraph


class AudioTranscriptionBase(SQLModel):
    name: str = Field(nullable=False)
    transcription: list[ASRParagraph] = Field(
        sa_column=Column(JSON),
    )
    validation: list[ASRParagraph] = Field(
        default_factory=list,
        sa_column=Column(JSON),
    )
    speaker_names: dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
    )


class AudioTranscription(AudioTranscriptionBase, table=True):
    __tablename__ = "audio_transcription"  # type: ignore[bad-override]
    id: uuid.UUID | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(), onupdate=func.now())
    )


class AudioTranscriptionCreate(AudioTranscriptionBase):
    pass


class AudioTranscriptionUpdate(SQLModel):
    name: str | None = None
    transcription: list[ASRParagraph] | None = None
    validation: list[ASRParagraph] | None = None
    speaker_names: dict[str, str] | None = None


class AudioTranscriptionRead(AudioTranscriptionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None = None
