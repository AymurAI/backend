import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, DateTime, func, text

if TYPE_CHECKING:
    from aymurai.database.meta.anonymization.paragraph import AnonymizationParagraph


class AnonymizationDocument(SQLModel, table=True):
    __tablename__ = "anonymization_document"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )

    name: str = Field(nullable=False)
    # paragraphs: list["AnonymizationParagraph"] = Relationship(
    #     link_model="AnonymizationDocumentParagraph"
    # )


class AnonymizationDocumentParagraph(SQLModel, table=True):
    __tablename__ = "anonymization_document_paragraph"
    document_id: uuid.UUID = Field(
        foreign_key="anonymization_document.id",
        primary_key=True,
    )
    paragraph_id: uuid.UUID = Field(foreign_key="anonymization_paragraph.id")
    order: int | None = Field(nullable=True)


class AnonymizationDocumentRead(BaseModel):
    id: uuid.UUID
    name: str
    paragraphs: list[uuid.UUID] | None
