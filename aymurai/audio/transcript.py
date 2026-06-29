import re
import warnings
from datetime import timedelta
from typing import Any


SENTENCE_END_RE = re.compile(r"(?:[.!?]+|[.!?]+[\"')\]]+)\s*$")


def parse_time_seconds(value: str | int | float | timedelta) -> float:
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    iso_match = re.fullmatch(
        r"PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?",
        text,
    )
    if iso_match:
        hours = float(iso_match.group(1) or 0)
        minutes = float(iso_match.group(2) or 0)
        seconds = float(iso_match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    hhmmss = text.split(":")
    if len(hhmmss) == 3:
        hours, minutes, seconds = hhmmss
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    return float(text)


def format_timestamp(seconds: float) -> str:
    normalized = max(0.0, seconds)
    whole_seconds = int(normalized)
    millis = int(round((normalized - whole_seconds) * 1000))
    if millis == 1000:
        whole_seconds += 1
        millis = 0
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _segment_value(segment: Any, field: str) -> Any:
    if isinstance(segment, dict):
        return segment.get(field)
    return getattr(segment, field)


def ends_sentence(text: str) -> bool:
    return bool(SENTENCE_END_RE.search(text.strip()))


def speaker_label(segment: dict[str, Any]) -> str:
    name = str(segment.get("speaker_name") or "").strip()
    if name:
        return name
    return f"Speaker {segment['speaker_no']}"


def diarized_segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Read diarized ASR paragraphs from a payload with a document field."""
    document = payload.get("document")
    if not isinstance(document, list) or not document:
        raise ValueError("Diarized response is missing a non-empty 'document' list")

    segments: list[dict[str, Any]] = []
    for index, item in enumerate(document):
        missing = [
            field
            for field in ("speaker_no", "start", "end", "text")
            if _segment_value(item, field) is None
        ]
        if missing:
            raise ValueError(
                f"document[{index}] is missing diarization field(s): {missing}"
            )

        speaker_no = _segment_value(item, "speaker_no")
        if str(speaker_no).strip() == "":
            raise ValueError(f"document[{index}] has an empty speaker label")

        text = str(_segment_value(item, "text") or "").strip()
        if not text:
            continue

        start = parse_time_seconds(_segment_value(item, "start"))
        end = parse_time_seconds(_segment_value(item, "end"))
        if start < 0 or end < start:
            raise ValueError(
                f"document[{index}] has invalid timestamps: start={start}, end={end}"
            )

        if isinstance(item, dict):
            segment = dict(item)
        else:
            segment = item.model_dump(mode="json")
        segment["_start_seconds"] = start
        segment["_end_seconds"] = end
        segment["_text"] = text
        segments.append(segment)

    if not segments:
        raise ValueError("Diarized response contains no non-empty speech segments")

    ordered = sorted(
        segments, key=lambda item: (item["_start_seconds"], item["_end_seconds"])
    )
    if [id(item) for item in ordered] != [id(item) for item in segments]:
        warnings.warn(
            "Diarized segments were not ordered by timestamp; transcript will be timestamp-sorted",
            stacklevel=2,
        )

    return ordered


def _new_turn(segment: dict[str, Any]) -> dict[str, Any]:
    return {
        "speaker": speaker_label(segment),
        "speaker_no": segment["speaker_no"],
        "start": segment["_start_seconds"],
        "end": segment["_end_seconds"],
        "texts": [segment["_text"]],
        "segments": [segment],
    }


def merge_speaker_turns_by_sentence(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    for segment in segments:
        label = speaker_label(segment)
        previous = turns[-1] if turns else None
        starts_new_turn = (
            previous is None
            or previous["speaker"] != label
            or ends_sentence(" ".join(previous["texts"]))
        )

        if starts_new_turn:
            turns.append(_new_turn(segment))
            continue

        previous["end"] = segment["_end_seconds"]
        previous["texts"].append(segment["_text"])
        previous["segments"].append(segment)

    for turn in turns:
        turn["text"] = " ".join(turn["texts"]).strip()
    return turns


def transcript_turns(payload: dict[str, Any]) -> list[dict[str, Any]]:
    turns = merge_speaker_turns_by_sentence(diarized_segments(payload))
    return serialize_speaker_turns(turns)


def serialize_speaker_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for turn in turns:
        serialized.append(
            {
                "speaker": turn["speaker"],
                "speaker_no": turn["speaker_no"],
                "start": format_timestamp(turn["start"]),
                "end": format_timestamp(turn["end"]),
                "text": turn.get("text") or " ".join(turn["texts"]).strip(),
                "segments": [
                    {
                        key: value
                        for key, value in segment.items()
                        if not key.startswith("_")
                    }
                    for segment in turn["segments"]
                ],
            }
        )
    return serialized


def markdown_transcript(payload: dict[str, Any], title: str) -> str:
    segments = diarized_segments(payload)
    turns = merge_speaker_turns_by_sentence(segments)

    distinct_speakers = {turn["speaker"] for turn in turns}
    if len(distinct_speakers) < 2:
        warnings.warn(
            f"Only one speaker label found for {title}; verify the source audio is expected to be single-speaker",
            stacklevel=2,
        )

    lines = [f"# {title}", ""]
    for turn in turns:
        timestamp = (
            f"{format_timestamp(turn['start'])} - {format_timestamp(turn['end'])}"
        )
        lines.append(f"## {turn['speaker']} ({timestamp})")
        lines.append("")
        lines.append(turn.get("text") or " ".join(turn["texts"]).strip())
        lines.append("")

    return "\n".join(lines).strip() + "\n"
