import uuid

from sqlmodel import Field, SQLModel


class AnonymizationDocumentParagraph(SQLModel, table=True):
    __tablename__ = "anonymization_document_paragraph"
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
