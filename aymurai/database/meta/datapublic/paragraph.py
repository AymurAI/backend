import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator
from typing_extensions import TYPE_CHECKING, Self
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import JSON, Column, DateTime, func, text

from aymurai.database.utils import text_to_uuid
from aymurai.meta.api_interfaces import DocLabel

if TYPE_CHECKING:
    from aymurai.database.meta.datapublic.document import DataPublicDocument

from aymurai.database.meta.datapublic.document_paragraph import (
    DataPublicDocumentParagraph,
)


class DataPublicParagraphBase(SQLModel):
    id: uuid.UUID | None = Field(None, primary_key=True)

    text: str = Field(nullable=False)
    prediction: list[DocLabel] | None = Field(None, sa_column=Column(JSON))
    validation: list[DocLabel] | None = Field(None, sa_column=Column(JSON))

    @model_validator(mode="after")
    def validate_text(self) -> Self:
        self.id = text_to_uuid(self.text)
        return self


class DataPublicParagraph(DataPublicParagraphBase, table=True):
    __tablename__ = "datapublic_paragraph"

    # NOTE: SQLModel with table=True does not run validators
    id: uuid.UUID | None = Field(None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )
    documents: list["DataPublicDocument"] = Relationship(
        back_populates="paragraphs",
        link_model=DataPublicDocumentParagraph,
    )


class DataPublicParagraphCreate(DataPublicParagraphBase):
    pass


class DataPublicParagraphUpdate(BaseModel):
    prediction: list[DocLabel] | None = None
    validation: list[DocLabel] | None = None


class DataPublicParagraphRead(BaseModel):
    id: uuid.UUID

    text: str
    prediction: list[DocLabel] | None
    validation: list[DocLabel] | None

    created_at: datetime
    updated_at: datetime | None
