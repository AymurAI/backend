import uuid

from pydantic import UUID5, BaseModel, Field, RootModel
from typing import Literal

from aymurai.meta.entities import EntityAttributes

from functools import cached_property


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
