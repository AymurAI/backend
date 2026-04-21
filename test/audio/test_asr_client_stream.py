from datetime import timedelta

from aymurai.api.meta.asr.websocket import WLKMessageTranscriptionLine
from aymurai.audio.asr_client import lines_to_paragraphs


def test_should_map_ws_lines_to_paragraphs_when_given_transcription_lines():
    lines = [
        WLKMessageTranscriptionLine(
            speaker=0,
            text="hola",
            start=timedelta(seconds=0),
            end=timedelta(seconds=1),
        ),
        WLKMessageTranscriptionLine(
            speaker=3,
            text="mundo",
            start=timedelta(seconds=1),
            end=timedelta(seconds=2),
        ),
    ]

    result = lines_to_paragraphs(lines)

    assert len(result) == 2
    assert result[0].speaker_no == 0
    assert result[0].text == "hola"
    assert result[0].start == timedelta(seconds=0)
    assert result[0].end == timedelta(seconds=1)
    assert result[1].speaker_no == 3
    assert result[1].text == "mundo"
    assert result[1].start == timedelta(seconds=1)
    assert result[1].end == timedelta(seconds=2)


def test_should_return_empty_list_when_given_empty_lines():
    result = lines_to_paragraphs([])
    assert result == []
