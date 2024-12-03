import uuid

from sqlmodel import Field, SQLModel


class DataPublicDocumentParagraph(SQLModel, table=True):
    __tablename__ = "datapublic_document_paragraph"
    document_id: uuid.UUID | None = Field(
        None,
        foreign_key="datapublic_document.id",
        primary_key=True,
    )
    paragraph_id: uuid.UUID | None = Field(
        None,
        foreign_key="datapublic_paragraph.id",
        primary_key=True,
    )
    order: int | None = Field(nullable=True)
