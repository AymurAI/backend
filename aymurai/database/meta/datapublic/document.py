import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, DateTime, func, text

from aymurai.database.meta.datapublic.document_paragraph import (
    DataPublicDocumentParagraph,
)

if TYPE_CHECKING:
    from aymurai.database.meta.datapublic.paragraph import DataPublicParagraph


class DataPublicDocument(SQLModel, table=True):
    __tablename__ = "datapublic_document"
    id: uuid.UUID | None = Field(None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )

    name: str = Field(nullable=False)
    paragraphs: list["DataPublicParagraph"] = Relationship(
        back_populates="documents",
        link_model=DataPublicDocumentParagraph,
    )


class DataPublicDocumentCreate(BaseModel):
    name: str
    # paragraphs: list["DataPublicParagraph"]


class DataPublicDocumentUpdate(BaseModel):
    name: str | None = None


class DataPublicDocumentRead(BaseModel):
    id: uuid.UUID
    name: str
    # paragraphs: list[uuid.UUID] | None
