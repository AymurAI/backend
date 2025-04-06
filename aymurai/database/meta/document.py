import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, DateTime, func, text, LargeBinary

from aymurai.database.meta.paragraph import Paragraph, ParagraphPublic


class Document(SQLModel, table=True):
    __tablename__ = "document"

    id: uuid.UUID | None = Field(None, primary_key=True)
    data: bytes = Field(
        sa_column=Column(LargeBinary),
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


class DocumentUpdate(BaseModel):
    name: str | None = None


class DocumentPublic(BaseModel):
    id: uuid.UUID
    name: str
    paragraphs: list[ParagraphPublic] | None = None
