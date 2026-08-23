import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, func, text
from sqlmodel import Field, SQLModel


class ValidatedDestinatarioBase(SQLModel):
    """Shared columns for a human-confirmed destinatario -> sector mapping."""

    document_id: uuid.UUID = Field(
        nullable=False,
        description="document_id of the DataExtraction this validation came from.",
    )
    nombre: str = Field(nullable=False)
    nombre_normalizado: str = Field(nullable=False, index=True)
    cargo: str | None = Field(default=None)
    cargo_normalizado: str | None = Field(default=None, index=True)
    sector: str = Field(nullable=False)


class ValidatedDestinatario(ValidatedDestinatarioBase, table=True):
    """
    One human-confirmed destinatario -> sector mapping, from one document.

    One row per (`document_id`, `nombre_normalizado`) -- re-validating the
    same document updates its row, but the same person validated again in a
    *different* document gets its own row, so history across documents isn't
    lost. `nombre_normalizado`/`cargo_normalizado` are
    `organigram_matching.normalize_text(...)` (lowercased, accent-stripped),
    used as exact-match lookup keys: first by nombre, falling back to cargo
    if no nombre match, to suggest a previously human-confirmed sector before
    falling back to the organigram inference (see
    `extraction_service._validated_candidate`).
    """

    __tablename__ = "llm_validated_destinatario"  # type: ignore[bad-override]
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": text("CURRENT_TIMESTAMP")}
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(), onupdate=func.now())
    )


class ValidatedDestinatarioCreate(ValidatedDestinatarioBase):
    pass


class ValidatedDestinatarioUpdate(SQLModel):
    nombre: str | None = None
    nombre_normalizado: str | None = None
    cargo: str | None = None
    cargo_normalizado: str | None = None
    sector: str | None = None


class ValidatedDestinatarioRead(ValidatedDestinatarioBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None
