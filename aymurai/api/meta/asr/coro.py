import re
from datetime import timedelta

from pydantic import BaseModel, ConfigDict

ISO8601_DURATION_RE = re.compile(
    r"^PT(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?$"
)


def _parse_hhmmss(value: str | int | float | timedelta) -> timedelta:
    """
    Parse a time value in HH:MM:SS format, ISO 8601 duration (PT#H#M#S), or seconds.

    Args:
        value (str | int | float | timedelta): The time value to parse.

    Raises:
        ValueError: If the value is not a valid time format.

    Returns:
        timedelta: The parsed time value.
    """
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
    return timedelta(
        hours=int(hours_str), minutes=int(minutes_str), seconds=float(seconds_str)
    )


class CoroSegment(BaseModel):
    """A speaker-attributed transcription segment from the coro done-frame."""

    model_config = ConfigDict(extra="ignore")

    start: float
    end: float
    text: str
    speaker: str
