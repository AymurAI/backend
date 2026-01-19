from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, field_validator


def _parse_hhmmss(value: str | int | float | timedelta) -> timedelta:
    if isinstance(value, timedelta):
        return value

    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))

    if not isinstance(value, str):
        raise ValueError("Invalid time format")

    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError("Expected HH:MM:SS format")

    hours_str, minutes_str, seconds_str = parts
    hours = int(hours_str)
    minutes = int(minutes_str)
    seconds = float(seconds_str)
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


class WLKMessageModelConfig(BaseModel):
    asr_model: str
    asr_backend: str
    diarization_model: str
    diarization_backend: str


class WLKMessageConfig(BaseModel):
    type: Literal["config"]
    useAudioWorklet: bool
    models: WLKMessageModelConfig


class WLKMessageTranscriptionLine(BaseModel):
    speaker: int
    text: str
    start: timedelta
    end: timedelta
    final: bool
    speaker_id: str | None = None
    detected_language: str | None = None

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_hhmmss(cls, value: str | int | float | timedelta) -> timedelta:
        return _parse_hhmmss(value)


class WLKMessageStatus(BaseModel):
    status: str
    lines: list[WLKMessageTranscriptionLine]
    buffer_transcription: str
    buffer_diarization: str
    buffer_translation: str
    remaining_time_transcription: float
    remaining_time_diarization: float
    speaker_ids: dict[str, str] | None = None


class WLKMessageSpeakerEmbeddings(BaseModel):
    type: Literal["speaker_embeddings"]
    speaker_ids: dict[str, str]
    speaker_id_bits: int
    models: WLKMessageModelConfig


class WLKMessageReadyToStopMessage(BaseModel):
    type: Literal["ready_to_stop"]


WLKMessageRawResponse = (
    WLKMessageConfig
    | WLKMessageStatus
    | WLKMessageSpeakerEmbeddings
    | WLKMessageReadyToStopMessage
)


class TranscriptionItem(BaseModel):
    speaker_no: int
    speaker_id: str
    start: timedelta
    end: timedelta
    text: str

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_hhmmss(cls, value: str | int | float | timedelta) -> timedelta:
        return _parse_hhmmss(value)
