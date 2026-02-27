import os

from aymurai.api.endpoints.routers.anonymizer.anonymizer import anonimize_audio
from aymurai.database.utils import data_to_uuid
from aymurai.meta.api_interfaces import (
    ASRDocument,
    ASRParagraph,
    DocLabel,
    DocumentAnnotations,
    DocumentInformation,
)
from aymurai.meta.entities import EntityAttributes
from aymurai.utils.cache import cache_save


def test_should_replace_entity_tokens_in_audio_output_when_annotations_match_asr_text(
    isolated_diskcache,
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
    cache_save(asr_doc, key=str(document_id))

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

    output_path = anonimize_audio(audio_bytes, annotations)
    try:
        assert output_path.exists()
        output_text = output_path.read_text(encoding="utf-8")
        assert "<PER>" in output_text
    finally:
        if output_path.exists():
            os.remove(output_path)
