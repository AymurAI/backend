import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator, computed_field
from typing_extensions import TYPE_CHECKING, Self
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import Column, DateTime, func, text

from aymurai.database.utils import text_to_uuid

if TYPE_CHECKING:
    from aymurai.database.meta.document import Document


class ParagraphBase(SQLModel):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)

    text: str = Field(nullable=False)

    @model_validator(mode="after")
    def validate_text(self) -> Self:
        self.id = text_to_uuid(self.text)
        return self

    @computed_field
    def hash(self) -> uuid.UUID:
        """Compute the hash of the text"""
        return text_to_uuid(self.text)


class Paragraph(ParagraphBase, table=True):
    __tablename__ = "paragraph"

    # NOTE: SQLModel with table=True does not run validators
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )

    fk_document: uuid.UUID = Field(None, foreign_key="document.id")
    document: "Document" = Relationship(back_populates="paragraphs")


class ParagraphUpdate(BaseModel):
    text: str | None = None


class ParagraphPublic(BaseModel):
    id: uuid.UUID

    text: str
    hash: uuid.UUID

    created_at: datetime
    updated_at: datetime | None
