import uuid

from sqlmodel import Field, SQLModel


class AnonymizationDocumentParagraph(SQLModel, table=True):
    __tablename__ = "anonymization_document_paragraph"
    # NOTE: The id is required to allow repition of document_id and paragraph_id
    # (the paragraph is repeated multiple times in the document)
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID | None = Field(
        None,
        foreign_key="anonymization_document.id",
        primary_key=True,
    )
    paragraph_id: uuid.UUID | None = Field(
        None,
        foreign_key="anonymization_paragraph.id",
        primary_key=True,
    )
    order: int | None = Field(nullable=True)
