import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import JSON, Column, DateTime, func, text
from sqlmodel import Field, Relationship, SQLModel

from aymurai.database.meta.document import Document


class DatapublicFormat(str, enum.Enum):
    NONE = "none"


class Datapublic(SQLModel, table=True):
    __tablename__ = "datapublic"

    id: uuid.UUID | None = Field(default_factory=uuid.uuid4, primary_key=True)

    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        sa_column=Column(DateTime(), onupdate=func.now())
    )

    validation_format: DatapublicFormat = DatapublicFormat.NONE

    records: dict = Field(sa_column=Column(JSON))

    fk_document: uuid.UUID | None = Field(foreign_key="document.id")
    document: Document | None = Relationship(back_populates="datapublic")


class DatapublicPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fk_document: uuid.UUID
    created_at: datetime
    updated_at: datetime | None = None
    validation_format: DatapublicFormat = DatapublicFormat.NONE
    records: dict = {}
