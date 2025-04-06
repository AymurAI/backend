import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator
from sqlalchemy import text
from sqlmodel import Field, SQLModel, Relationship
from aymurai.database.utils import text_to_uuid

from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from aymurai.database.meta.prediction import Prediction


class ModelBase(SQLModel):
    id: uuid.UUID | None = Field(None, primary_key=True)

    name: str = Field(nullable=False)
    version: str = Field(nullable=False)

    @model_validator(mode="after")
    def validate_name_version(self) -> "ModelBase":
        self.id = text_to_uuid(f"{self.name}-{self.version}")
        return self


class Model(ModelBase, table=True):
    __tablename__ = "model"

    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )

    predictions: list["Prediction"] = Relationship(back_populates="model")

    # @model_validator(mode="before")
    # def generate_id(cls, values: dict):
    #     if values.get("id") is None and set(values.keys()) & {"name", "version"}:
    #         values["id"] = text_to_uuid(f"{values['name']}-{values['version']}")
    #     return values


class ModelCreate(ModelBase):
    def compile(self) -> Model:
        return Model(**self.model_dump())


class ModelPublic(BaseModel):
    id: uuid.UUID
    name: str
    version: str

    created_at: datetime
