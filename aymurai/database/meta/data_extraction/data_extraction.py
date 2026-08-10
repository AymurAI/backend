import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, func, text
from sqlmodel import Field, SQLModel


class DataExtractionBase(SQLModel):
    """
    Shared columns for a persisted data-extraction result.

    Note:
        Unlike `SummarizationBase` (where `summary`/`validation` are different
        artifacts -- markdown vs. the frontend's TipTap rich-text document --
        and must not share a type), `prediction` and `validation` here ARE the
        same shape: both are (a subset of) `DataExtractionResult`. The
        data-extraction frontend reviews/corrects structured fields (nombre,
        cargo, sector, tema, subtema, ...) through form fields and dropdowns,
        not a rich-text editor, so there's no separate artifact type to model.
    """

    document: list[str] = Field(sa_column=Column(JSON))
    prediction: dict = Field(sa_column=Column(JSON))
    validation: dict | None = Field(default=None, sa_column=Column(JSON))
    config: dict = Field(sa_column=Column(JSON))


class DataExtraction(DataExtractionBase, table=True):
    """A data-extraction row, keyed by the source Document's `document_id`."""

    __tablename__ = "llm_data_extraction"  # type: ignore[bad-override]
    id: uuid.UUID | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(), onupdate=func.now())
    )


class DataExtractionCreate(DataExtractionBase):
    pass


class DataExtractionUpdate(SQLModel):
    document: list[str] | None = None
    prediction: dict | None = None
    validation: dict | None = None
    config: dict | None = None


class DataExtractionRead(DataExtractionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime | None = None
