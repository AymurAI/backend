import os

from sqlmodel import Session

from aymurai.api.endpoints.routers.anonymizer.anonymizer import anonymize_audio
from aymurai.database.crud.audio_transcription import (
    audio_transcription_create_or_update,
)
from aymurai.database.utils import data_to_uuid
from aymurai.meta.api_interfaces import (
    ASRDocument,
    ASRParagraph,
    DocLabel,
    DocumentAnnotations,
    DocumentInformation,
)
from aymurai.meta.entities import EntityAttributes


def test_should_replace_entity_tokens_in_audio_output_when_annotations_match_asr_text(
    sqlite_engine,
    make_wav_bytes,
):
    audio_bytes = make_wav_bytes(freq_hz=330)
    document_id = data_to_uuid(audio_bytes)

    asr_doc = ASRDocument(
        document_id=document_id,
        document=[
            ASRParagraph.model_construct(
                speaker_no=1,
                start=0.0,
                end=1.0,
                text="Juan Perez declaro en audiencia",
            )
        ],
    )
    annotations = DocumentAnnotations(
        data=[
            DocumentInformation(
                document="Juan Perez declaro en audiencia",
                labels=[
                    DocLabel(
                        text="Juan Perez",
                        start_char=0,
                        end_char=10,
                        attrs=EntityAttributes(
                            aymurai_label="PER",
                            aymurai_alt_text=None,
                            aymurai_alt_start_char=None,
                            aymurai_alt_end_char=None,
                            aymurai_method=None,
                            aymurai_score=None,
                            canonical_entity_id=None,
                        ),
                    )
                ],
            )
        ]
    )

    with Session(sqlite_engine) as session:
        audio_transcription_create_or_update(
            transcription_id=document_id,
            name="test.wav",
            transcription=asr_doc.document,
            session=session,
        )
        output_path = anonymize_audio(audio_bytes, annotations, session=session)

    try:
        assert output_path.exists()
        output_text = output_path.read_text(encoding="utf-8")
        assert "<PER>" in output_text
    finally:
        if output_path.exists():
            os.remove(output_path)
