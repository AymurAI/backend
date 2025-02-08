import uuid

from pydantic import UUID5, AliasChoices, BaseModel, Field

from aymurai.meta.entities import EntityAttributes


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


class Document(BaseModel):
    document: list[str]
    document_id: UUID5
    header: list[str] | None = None
    footer: list[str] | None = None
