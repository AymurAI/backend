import uuid

from pydantic import UUID5, BaseModel, Field, RootModel

from aymurai.meta.entities import DocLabel


class SuccessResponse(BaseModel):
    id: int | uuid.UUID | None = None
    msg: str | None = None


class TextRequest(BaseModel):
    """Datatype for a text span request"""

    text: str = Field(
        ...,
        description="text field to run prediction",
    )


class DocumentInformation(BaseModel):
    """Datatype for a document information with all labels"""

    document: str = Field(description="processed text")
    labels: list[DocLabel] | None = None


class DocumentAnnotations(BaseModel):
    """Datatype for document annotations"""

    data: list[DocumentInformation]


# class Document(BaseModel):
#     document: list[str]
#     document_id: UUID5
#     header: list[str] | None = None
#     footer: list[str] | None = None
class DataPublicDocumentAnnotations(RootModel):
    """Datatype for document annotations"""

    root: dict


class Document(BaseModel):
    document: list[str]
    document_id: UUID5
    header: list[str] | None = None
    footer: list[str] | None = None
