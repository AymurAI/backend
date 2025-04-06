import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator
from sqlmodel import Field, SQLModel, Relationship
from sqlalchemy import JSON, Column, DateTime, func, text

from aymurai.meta.api_interfaces import DocLabel

from aymurai.database.meta.model import ModelPublic
from typing import TYPE_CHECKING
from aymurai.database.utils import text_to_hash

# if TYPE_CHECKING:
from aymurai.database.schema import Model, Paragraph


class PredictionBase(SQLModel):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)

    input: str = Field(nullable=False)
    input_hash: str | None = None

    prediction: list[DocLabel] | None = Field(None, sa_column=Column(JSON))
    validation: list[DocLabel] | None = Field(None, sa_column=Column(JSON))

    fk_model: uuid.UUID = Field(foreign_key="model.id")
    fk_paragraph: uuid.UUID | None = Field(None, foreign_key="paragraph.id")

    @model_validator(mode="after")
    def validate_input(self) -> "PredictionBase":
        self.input_hash = text_to_hash(self.input)
        return self


class Prediction(PredictionBase, table=True):
    __tablename__ = "prediction"

    input_hash: str

    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )

    model: "Model" = Relationship(back_populates="predictions")
    paragraph: Paragraph | None = Relationship(back_populates="predictions")


class PredictionCreate(PredictionBase):
    def compile(self) -> Prediction:
        return Prediction(**self.model_dump())


class PredictionPublic(BaseModel):
    """Datatype for a prediction"""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None = None

    input: str
    prediction: list[DocLabel] = Field(default_factory=list)
    validation: list[DocLabel] = Field(default_factory=list)

    model: ModelPublic
