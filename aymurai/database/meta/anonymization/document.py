import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime, func, text


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


class AnonymizationDocumentParagraph(SQLModel, table=True):
    __tablename__ = "anonymization_document_paragraph"
    document_id: uuid.UUID = Field(
        foreign_key="anonymization_document.id",
        primary_key=True,
    )
    paragraph_id: uuid.UUID = Field(foreign_key="anonymization_paragraph.id")
    order: int | None = Field(nullable=True)


class DocumentRead(BaseModel):
    pass
