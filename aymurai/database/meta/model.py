import enum
import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Field, Relationship, SQLModel
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from aymurai.database.meta.prediction import Prediction


class ModelType(str, enum.Enum):
    ANONYMIZATION = "anonymization"
    DATAPUBLIC = "datapublic"


class ModelBase(SQLModel):
    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)

    name: str = Field(nullable=False)
    version: str = Field(nullable=False)

    type: ModelType = Field(nullable=False)
    pipeline_path: str = Field(nullable=False)


class Model(ModelBase, table=True):
    __tablename__ = "model"

    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )

    predictions: list["Prediction"] = Relationship(back_populates="model")


class ModelCreate(ModelBase):
    def compile(self) -> Model:
        return Model(**self.model_dump())


class ModelPublic(BaseModel):
    id: uuid.UUID

    type: ModelType
    name: str
    version: str
    pipeline_path: str

    created_at: datetime
