import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, DateTime, func, text

from aymurai.database.meta.anonymization.document_paragraph import (
    AnonymizationDocumentParagraph,
)

if TYPE_CHECKING:
    from aymurai.database.meta.anonymization.paragraph import AnonymizationParagraph


class AnonymizationDocument(SQLModel, table=True):
    __tablename__ = "anonymization_document"
    id: uuid.UUID | None = Field(None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )

    name: str = Field(nullable=False)
    paragraphs: list["AnonymizationParagraph"] = Relationship(
        back_populates="documents", link_model=AnonymizationDocumentParagraph
    )


class AnonymizationDocumentCreate(BaseModel):
    name: str
    # paragraphs: list["AnonymizationParagraph"]


class AnonymizationDocumentUpdate(BaseModel):
    name: str | None = None


class AnonymizationDocumentRead(BaseModel):
    id: uuid.UUID
    name: str
    # paragraphs: list[uuid.UUID] | None
