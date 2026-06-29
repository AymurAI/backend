from datetime import timedelta

import pytest

from aymurai.audio.transcript import (
    diarized_segments,
    ends_sentence,
    markdown_transcript,
    merge_speaker_turns_by_sentence,
)
from aymurai.meta.api_interfaces import ASRParagraph


def _paragraph(
    speaker_no: int,
    start: float,
    end: float,
    text: str,
    speaker_name: str | None = None,
) -> ASRParagraph:
    return ASRParagraph(
        speaker_no=speaker_no,
        speaker_name=speaker_name,
        start=timedelta(seconds=start),
        end=timedelta(seconds=end),
        text=text,
    )


def test_ends_sentence_detects_sentence_closing_punctuation():
    assert ends_sentence("Hola.")
    assert ends_sentence("Hola?")
    assert ends_sentence("Hola!")
    assert ends_sentence("¿Se entiende?")
    assert ends_sentence("¡Perfecto!")
    assert ends_sentence("Bueno...")


def test_ends_sentence_ignores_non_final_punctuation_and_open_text():
    assert not ends_sentence("entonces,")
    assert not ends_sentence("lo que queria decir es")
    assert not ends_sentence("pero bueno:")
    assert not ends_sentence("")


def test_merge_combines_consecutive_same_speaker_without_sentence_close():
    segments = diarized_segments(
        {
            "document": [
                _paragraph(1, 0.0, 1.0, "Nos quedamos,"),
                _paragraph(1, 1.0, 2.0, "esperando en el lobby"),
            ]
        }
    )

    turns = merge_speaker_turns_by_sentence(segments)

    assert len(turns) == 1
    assert turns[0]["speaker"] == "Speaker 1"
    assert turns[0]["speaker_no"] == 1
    assert turns[0]["start"] == 0.0
    assert turns[0]["end"] == 2.0
    assert turns[0]["text"] == "Nos quedamos, esperando en el lobby"
    assert len(turns[0]["segments"]) == 2


def test_merge_splits_same_speaker_after_sentence_close():
    segments = diarized_segments(
        {
            "document": [
                _paragraph(1, 0.0, 1.0, "Hola."),
                _paragraph(1, 1.0, 2.0, "Seguimos con otro tema"),
            ]
        }
    )

    turns = merge_speaker_turns_by_sentence(segments)

    assert [turn["text"] for turn in turns] == [
        "Hola.",
        "Seguimos con otro tema",
    ]
    assert turns[0]["end"] == 1.0
    assert turns[1]["start"] == 1.0


def test_merge_splits_when_speaker_changes_even_without_sentence_close():
    segments = diarized_segments(
        {
            "document": [
                _paragraph(1, 0.0, 1.0, "Entonces,"),
                _paragraph(2, 1.0, 2.0, "contesto yo"),
            ]
        }
    )

    turns = merge_speaker_turns_by_sentence(segments)

    assert [turn["speaker"] for turn in turns] == ["Speaker 1", "Speaker 2"]
    assert [turn["text"] for turn in turns] == ["Entonces,", "contesto yo"]


def test_merge_preserves_timestamps_across_merged_segments():
    segments = diarized_segments(
        {
            "document": [
                _paragraph(1, 5.76, 6.24, "Nos quedamos,"),
                _paragraph(1, 6.24, 12.48, "esperando en el lobby."),
            ]
        }
    )

    turns = merge_speaker_turns_by_sentence(segments)

    assert turns[0]["start"] == 5.76
    assert turns[0]["end"] == 12.48


def test_merge_uses_speaker_name_when_available():
    segments = diarized_segments(
        {
            "document": [
                _paragraph(1, 0.0, 1.0, "Tiene la palabra,", "Jueza"),
                _paragraph(1, 1.0, 2.0, "doctora.", "Jueza"),
            ]
        }
    )

    turns = merge_speaker_turns_by_sentence(segments)

    assert turns[0]["speaker"] == "Jueza"
    assert turns[0]["speaker_no"] == 1


def test_diarized_segments_ignores_empty_text_segments():
    segments = diarized_segments(
        {
            "document": [
                _paragraph(1, 0.0, 1.0, "  "),
                _paragraph(1, 1.0, 2.0, "Texto util"),
            ]
        }
    )

    assert len(segments) == 1
    assert segments[0]["_text"] == "Texto util"


def test_markdown_transcript_uses_sentence_aware_turns():
    with pytest.warns(UserWarning, match="Only one speaker label"):
        markdown = markdown_transcript(
            {
                "document": [
                    _paragraph(1, 0.0, 1.0, "Hola."),
                    _paragraph(1, 1.0, 2.0, "Seguimos."),
                ]
            },
            title="Audiencia",
        )

    assert "## Speaker 1 (00:00:00.000 - 00:00:01.000)" in markdown
    assert "## Speaker 1 (00:00:01.000 - 00:00:02.000)" in markdown
    assert "Hola.\n\n## Speaker 1" in markdown
