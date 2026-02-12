import uuid

from pydantic import UUID4, UUID5, BaseModel, Field, RootModel, computed_field

from aymurai.api.meta.asr.websocket import TranscriptionItem
from aymurai.database.utils import text_to_uuid
from aymurai.meta.entities import EntityAttributes

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


class DocumentAnnotations(BaseModel):
    """Datatype for document annotations"""

    data: list[DocumentInformation]


class DataPublicDocumentAnnotations(RootModel):
    """Datatype for document annotations"""

    root: dict


class Document(BaseModel):
    document: list[str]
    document_id: UUID5
    header: list[str] | None = None
    footer: list[str] | None = None


class ASRParagraph(TranscriptionItem):
    @computed_field
    @property
    def paragraph_id(self) -> UUID:
        return text_to_uuid(self.text)

    def to_txt(self) -> str:
        return "\n".join(
            [
                f"{self.start:.2f}s - {self.end:.2f}s",
                f"speaker {self.speaker_no}",
                self.text,
            ]
        )


class ASRDocument(BaseModel):
    document: list[ASRParagraph]
    document_id: UUID

    def to_txt(self) -> str:
        return "\n\n".join([paragraph.to_txt() for paragraph in self.document])
