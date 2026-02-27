import re
from datetime import timedelta
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, field_validator

ISO8601_DURATION_RE = re.compile(
    r"^PT(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?$"
)


def _parse_hhmmss(value: str | int | float | timedelta) -> timedelta:
    if isinstance(value, timedelta):
        return value

    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))

    if not isinstance(value, str):
        raise ValueError("Invalid time format")

    if value.startswith("PT"):
        match = ISO8601_DURATION_RE.match(value)
        if match is None:
            raise ValueError("Expected ISO 8601 duration format (PT#H#M#S)")

        hours = float(match.group("hours") or 0)
        minutes = float(match.group("minutes") or 0)
        seconds = float(match.group("seconds") or 0)

        return timedelta(hours=hours, minutes=minutes, seconds=seconds)

    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError("Expected HH:MM:SS format")

    hours_str, minutes_str, seconds_str = parts
    hours = int(hours_str)
    minutes = int(minutes_str)
    seconds = float(seconds_str)
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


class WLKMessageConfig(BaseModel):
    type: Literal["config"]
    useAudioWorklet: bool


class WLKMessageTranscriptionLine(BaseModel):
    speaker: int
    text: str
    start: timedelta
    end: timedelta
    detected_language: str | None = None

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: str | None) -> str:
        if value is None:
            return ""
        return value

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


class WLKMessageReadyToStopMessage(BaseModel):
    type: Literal["ready_to_stop"]


WLKMessageRawResponse = (
    WLKMessageConfig | WLKMessageStatus | WLKMessageReadyToStopMessage
)


class TranscriptionItem(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    speaker_no: int
    start: timedelta
    end: timedelta
    text: str

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_hhmmss(cls, value: str | int | float | timedelta) -> timedelta:
        return _parse_hhmmss(value)
