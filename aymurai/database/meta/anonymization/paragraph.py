import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from typing_extensions import Self
from sqlmodel import Field, SQLModel
from pydantic import BaseModel, model_validator
from sqlalchemy import JSON, Column, DateTime, func, text

from aymurai.database.utils import text_to_uuid
from aymurai.meta.api_interfaces import DocLabel

if TYPE_CHECKING:
    pass


class AnonymizationParagraph(SQLModel, table=True):
    __tablename__ = "anonymization_paragraph"

    # NOTE: SQLModel with table=True does not run validators
    id: uuid.UUID | None = Field(None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )

    text: str = Field(nullable=False)
    prediction: list[DocLabel] | None = Field(sa_column=Column(JSON))
    validation: list[DocLabel] | None = Field(sa_column=Column(JSON))

    def _set_id(self):
        self.id = text_to_uuid(self.text)


class AnonymizationParagraphCreate(BaseModel):
    id: uuid.UUID | None = None

    text: str
    prediction: list[DocLabel] | None = None
    validation: list[DocLabel] | None = None

    @model_validator(mode="after")
    def validate_text(self) -> Self:
        self.id = text_to_uuid(self.text)
        return self


class AnonymizationParagraphUpdate(BaseModel):
    prediction: list[DocLabel] | None = None
    validation: list[DocLabel] | None = None


class AnonymizationParagraphRead(BaseModel):
    id: uuid.UUID

    text: str
    prediction: list[DocLabel] | None
    validation: list[DocLabel] | None

    created_at: datetime
    updated_at: datetime | None
