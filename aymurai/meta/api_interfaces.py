from __future__ import annotations

import uuid
from datetime import timedelta
from functools import cached_property
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import (
    UUID4,
    UUID5,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    computed_field,
    field_validator,
)

from aymurai.api.meta.asr.coro import _parse_hhmmss
from aymurai.database.utils import text_to_uuid
from aymurai.meta.entities import EntityAttributes

if TYPE_CHECKING:
    from aymurai.database.meta.audio_transcription import AudioTranscriptionRead

UUID = UUID4 | UUID5


class SuccessResponse(BaseModel):
    id: int | uuid.UUID | None = None
    msg: str | None = None


class TextRequest(BaseModel):
    """Datatype for a text span request"""

    text: str = Field(
        ...,
        description="text field to run prediction",
    )


class DocLabel(BaseModel):
    """Datatype for a document label"""

    text: str = Field(
        description="raw text of entity",
        # alias=AliasChoices(["text", "document"]),
    )
    start_char: int = Field(
        description="start character of the span in relation of the full text"
    )
    end_char: int = Field(
        description="last character of the span in relation of the full text"
    )
    attrs: EntityAttributes


class DocumentInformation(BaseModel):
    """Datatype for a document information with all labels"""

    document: str = Field(description="processed text")
    labels: list[DocLabel] = Field(default_factory=list)


class LabelPolicy(BaseModel):
    """Per-label policy for disambiguation and anonymization."""

    anonymize: bool | None = None
    disambiguation: Literal["none", "fuzzy", "llm"] | None = None
    use_subclass_when_available: bool | None = None


class RenderPolicy(BaseModel):
    """Render policy for anonymized tokens."""

    suffix_mode: Literal["auto", "always", "never"] | None = None
    suffix_threshold: int | None = None


class DocumentAnnotations(BaseModel):
    """Datatype for document annotations"""

    data: list[DocumentInformation]
    label_policies: dict[str, LabelPolicy] | None = None
    render_policy: RenderPolicy | None = None


class DataPublicDocumentAnnotations(RootModel):
    """Datatype for document annotations"""

    root: dict


class Document(BaseModel):
    document: list[str]
    document_id: UUID5
    header: list[str] | None = None
    footer: list[str] | None = None


class ASRParagraph(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    speaker_no: int
    speaker_name: str | None = None
    start: timedelta
    end: timedelta
    text: str

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_hhmmss(cls, value: str | int | float | timedelta) -> timedelta:
        return _parse_hhmmss(value)

    @computed_field
    @property
    def paragraph_id(self) -> UUID:
        return text_to_uuid(self.text)

    @staticmethod
    def _format_hh_mm_ss(value: timedelta | float | int | str) -> str:
        if isinstance(value, timedelta):
            total_seconds = value.total_seconds()
        elif isinstance(value, str):
            return value
        else:
            total_seconds = float(value)

        seconds = max(0, int(total_seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def to_txt(self) -> str:
        start = self._format_hh_mm_ss(self.start)
        end = self._format_hh_mm_ss(self.end)
        name = (self.speaker_name or "").strip()
        speaker_label = name or str(self.speaker_no)
        return "\n".join(
            [
                f"{start} - {end}",
                f"speaker {speaker_label}",
                self.text,
            ]
        )


class ASRParagraphRequest(BaseModel):
    speaker_no: int
    speaker_name: str | None = None
    start: str | float | int
    end: str | float | int
    text: str


class ASRDocument(BaseModel):
    document: list[ASRParagraph]
    document_id: UUID

    def to_txt(self) -> str:
        return "\n\n".join([paragraph.to_txt() for paragraph in self.document])

    @classmethod
    def from_transcription(cls, transcription: AudioTranscriptionRead) -> ASRDocument:
        return cls(
            document=transcription.validation or transcription.transcription,
            document_id=transcription.id,
        )


class PromptSet(BaseModel):
    label: str
    system: str
    user: str


class PromptLibrary(RootModel):
    root: list[PromptSet] = Field(default_factory=list)

    @cached_property
    def as_dict(self) -> dict[str, PromptSet]:
        return {p.label: p for p in self.root}

    def get(self, label: str) -> PromptSet | None:
        return self.as_dict.get(label)
