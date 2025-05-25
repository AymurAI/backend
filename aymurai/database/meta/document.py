import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, LargeBinary, func, text
from sqlalchemy.orm import deferred
from sqlmodel import Field, Relationship, SQLModel

from aymurai.database.meta.paragraph import ParagraphPublic

if TYPE_CHECKING:
    from aymurai.database.meta.datapublic import Datapublic
    from aymurai.database.meta.paragraph import Paragraph, ParagraphPublic


class Document(SQLModel, table=True):
    __tablename__ = "document"

    id: uuid.UUID | None = Field(None, primary_key=True)
    data: bytes = Field(
        sa_column=deferred(Column(LargeBinary)),
        description="binary data of the document",
    )
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )

    name: str = Field(nullable=False)

    paragraphs: list["Paragraph"] = Relationship(back_populates="document")
    datapublic: list["Datapublic"] = Relationship(back_populates="document")


class DocumentUpdate(BaseModel):
    name: str | None = None


class DocumentPublic(BaseModel):
    id: uuid.UUID
    name: str
    paragraphs: list[ParagraphPublic] | None = None
