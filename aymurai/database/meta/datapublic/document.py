import uuid
from datetime import datetime

from typing import TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, DateTime, func, text, JSON
from aymurai.meta.api_interfaces import DataPublicDocumentAnnotations

from aymurai.database.meta.datapublic.document_paragraph import (
    DataPublicDocumentParagraph,
)

if TYPE_CHECKING:
    from aymurai.database.meta.datapublic.paragraph import DataPublicParagraph


class DataPublicDocumentBase(SQLModel):
    prediction: DataPublicDocumentAnnotations | None = Field(
        None, sa_column=Column(JSON)
    )
    validation: DataPublicDocumentAnnotations | None = Field(
        None, sa_column=Column(JSON)
    )


class DataPublicDocument(DataPublicDocumentBase, table=True):
    __tablename__ = "datapublic_document"
    id: uuid.UUID | None = Field(None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )

    paragraphs: list["DataPublicParagraph"] = Relationship(
        back_populates="documents",
        link_model=DataPublicDocumentParagraph,
    )


class DataPublicDocumentCreate(DataPublicDocumentBase):
    pass


class DataPublicDocumentUpdate(DataPublicDocumentBase):
    prediction: DataPublicDocumentAnnotations | None = None
    validation: DataPublicDocumentAnnotations | None = None


class DataPublicDocumentRead(DataPublicDocumentBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None = None
